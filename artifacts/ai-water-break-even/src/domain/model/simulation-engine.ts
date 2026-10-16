/**
 * Vectorized, zero-allocation Monte Carlo engine for the AI water
 * break-even model.
 *
 * Path equations (per simulated path, year t = 1..horizon):
 *
 *   W_b(t) = W₀ · (1 + g_ai)^t · (1 − e_water)^t
 *   W_s(t) = S₀ · 1.022^t · (adoption · (1 − e^(−0.105·t))) · E_int · R · F_attr
 *
 * The inner loop evaluates both by iterative compounding, which is
 * algebraically identical to the closed forms above but replaces every
 * Math.pow / Math.exp with a multiply:
 *
 *   burden:  r = (1 + g)(1 − e);  r^t maintained by bg *= r
 *   savings: k = S₀·adoption·E_int·R·F_attr;  1.022^t·(1 − q^t) with
 *            q = e^(−0.105) precomputed, tracked as (powA − powB).
 *
 * Sustained break-even: a path breaks even at year T iff balance(t) ≥ 0
 * for all t in [T, horizon]. We find the last negative year by scanning
 * backwards from the horizon; the break-even year is lastNegative + 1
 * (or year 1 if the path is never negative, or −1 if the final year is
 * still negative — it can never recover after that).
 */

import { FastPRNG } from '../math/prng';
import { bandOfSorted, copyColumn, medianOfInt32 } from '../math/statistics';
import {
  DEFAULT_CONFIG,
  PARAMETER_KEYS,
  PARAMETER_LABELS,
  type ParameterKey,
  type PercentileSeries,
  type ScenarioConfig,
  type SensitivityMetric,
  type SensitivityResult,
  type SummaryWire,
} from './types';

/** Adoption lag factor: e^(−0.105) — half-life of the S-curve ≈ 6.6 years. */
const ADOPTION_LAG = Math.exp(-0.105);
/** Annual growth of the savings potential base. */
const SAVINGS_GROWTH = 1.022;

/** Chunk of simulations processed between cancellation/progress checks. */
export const SIMULATION_CHUNK = 2500;

/** Sensitivity passes cap the run count to stay interactive. */
const SENSITIVITY_SIM_CAP = 1200;
/** Scenario comparison cap. */
const SCENARIO_SIM_CAP = 2500;

export interface EngineMatrices {
  burden: Float64Array;
  savings: Float64Array;
  balance: Float64Array;
  /** Sustained break-even year (1-based), or −1 when never reached. */
  breakEvenYears: Int32Array;
  simulations: number;
  horizon: number;
}

/** Pre-allocate the contiguous simulation matrices. */
export function allocateMatrices(simulations: number, horizon: number): EngineMatrices {
  const cells = simulations * horizon;
  return {
    burden: new Float64Array(cells),
    savings: new Float64Array(cells),
    balance: new Float64Array(cells),
    breakEvenYears: new Int32Array(simulations),
    simulations,
    horizon,
  };
}

/** Clamp a config to its legal bounds so every engine entry is total. */
export function sanitizeConfig(config: ScenarioConfig): ScenarioConfig {
  const clamp = (value: number, min: number, max: number) =>
    Math.min(max, Math.max(min, Number.isFinite(value) ? value : min));
  return {
    ...config,
    startingWaterUse: clamp(config.startingWaterUse, 0, 800),
    aiGrowthRate: clamp(config.aiGrowthRate, 0, 0.2),
    efficiencyImprovement: clamp(config.efficiencyImprovement, 0, 0.08),
    savingsPotential: clamp(config.savingsPotential, 0, 2000),
    interventionEffectiveness: clamp(config.interventionEffectiveness, 0, 1),
    adoptionRate: clamp(config.adoptionRate, 0, 1),
    realizationFactor: clamp(config.realizationFactor, 0, 1),
    attributionFraction: clamp(config.attributionFraction, 0, 1),
    horizon: Math.round(clamp(config.horizon, 10, 80)),
    simulations: Math.round(clamp(config.simulations, 250, 20000)),
    seed: Math.round(clamp(config.seed, 1, 999999999)),
  };
}

/**
 * Simulate paths [from, to) of the matrix block using the supplied PRNG.
 * The RNG instance is threaded across chunks so a run split into chunks is
 * bit-identical to a single-shot run. Allocates nothing.
 */
export function simulateChunk(
  config: ScenarioConfig,
  matrices: EngineMatrices,
  rng: FastPRNG,
  from: number,
  to: number,
): void {
  const { horizon } = matrices;
  const { burden, savings, balance, breakEvenYears } = matrices;

  for (let sim = from; sim < to; sim++) {
    // --- Sample the eight uncertain parameters for this path. ---
    const sWater = Math.max(0, config.startingWaterUse * Math.exp(rng.nextNormal(0, 0.12)));
    const gAI = rng.nextTruncatedNormal(config.aiGrowthRate, 0.012, 0, 0.3);
    const effGain = rng.nextTruncatedNormal(config.efficiencyImprovement, 0.004, 0, 0.12);
    const sPot = Math.max(0, config.savingsPotential * Math.exp(rng.nextNormal(0, 0.16)));
    const intEff = rng.nextTruncatedNormal(config.interventionEffectiveness, 0.09, 0, 1);
    const maxAdopt = rng.nextTruncatedNormal(config.adoptionRate, 0.1, 0, 1);
    const realFactor = rng.nextTruncatedNormal(config.realizationFactor, 0.09, 0, 1);
    const attrFrac = rng.nextTruncatedNormal(config.attributionFraction, 0.1, 0, 1);

    const burdenRate = (1 + gAI) * (1 - effGain);
    const savingsScale = sPot * maxAdopt * intEff * realFactor * attrFrac;
    const laggedGrowth = SAVINGS_GROWTH * ADOPTION_LAG;

    let burdenPow = 1; // r^t
    let savingsPowA = SAVINGS_GROWTH; // 1.022^t
    let savingsPowB = laggedGrowth; // (1.022·q)^t
    let cumBurden = 0;
    let cumSavings = 0;
    const offset = sim * horizon;

    for (let year = 1; year <= horizon; year++) {
      burdenPow *= burdenRate;
      savingsPowA *= SAVINGS_GROWTH;
      savingsPowB *= laggedGrowth;

      cumBurden += sWater * burdenPow;
      cumSavings += savingsScale * (savingsPowA - savingsPowB);

      const idx = offset + year - 1;
      burden[idx] = cumBurden;
      savings[idx] = cumSavings;
      balance[idx] = cumSavings - cumBurden;
    }

    // --- Sustained break-even: backwards scan for the last negative year. ---
    let lastNegativeIdx = -1;
    for (let idx = offset + horizon - 1; idx >= offset; idx--) {
      if (balance[idx] < 0) {
        lastNegativeIdx = idx - offset;
        break;
      }
    }
    if (lastNegativeIdx === horizon - 1) {
      breakEvenYears[sim] = -1; // Still negative at the horizon: never.
    } else {
      breakEvenYears[sim] = lastNegativeIdx + 2; // 1-based crossing year.
    }
  }
}

/** Reusable extraction workspace: scratch column + median scratch. */
export interface ExtractionBuffers {
  column: Float64Array;
  intScratch: Int32Array;
}

export function allocateExtraction(simulations: number, horizon: number): ExtractionBuffers {
  return {
    column: new Float64Array(simulations),
    intScratch: new Int32Array(simulations),
  };
}

/**
 * Reduce the matrices to the wire summary: five quantiles per year for the
 * burden, savings, and balance curves, packed row-major per curve as
 * [p5 | p25 | median | p75 | p95], plus the break-even distribution.
 * Returns freshly allocated typed arrays intended for transfer.
 */
export function summarizeMatrices(
  matrices: EngineMatrices,
  config: ScenarioConfig,
  buffers: ExtractionBuffers,
): SummaryWire {
  const { simulations, horizon } = matrices;
  const { column, intScratch } = buffers;
  const pack = (matrix: Float64Array): Float64Array => {
    const packed = new Float64Array(5 * horizon);
    for (let year = 0; year < horizon; year++) {
      copyColumn(matrix, simulations, horizon, year, column);
      column.sort(); // In-place numeric sort of the contiguous slice.
      const band = bandOfSorted(column, simulations);
      packed[year] = band.p5;
      packed[horizon + year] = band.p25;
      packed[2 * horizon + year] = band.median;
      packed[3 * horizon + year] = band.p75;
      packed[4 * horizon + year] = band.p95;
    }
    return packed;
  };

  const breakEvenYearCounts = new Int32Array(horizon);
  let neverCount = 0;
  let by10 = 0;
  let by20 = 0;
  let by30 = 0;
  let by50 = 0;
  const cutoff50 = Math.min(50, horizon);
  const cutoff30 = Math.min(30, horizon);
  const cutoff20 = Math.min(20, horizon);
  const cutoff10 = Math.min(10, horizon);
  for (let sim = 0; sim < simulations; sim++) {
    const year = matrices.breakEvenYears[sim];
    if (year <= 0) {
      neverCount++;
      continue;
    }
    breakEvenYearCounts[year - 1]++;
    if (year <= cutoff10) by10++;
    if (year <= cutoff20) by20++;
    if (year <= cutoff30) by30++;
    if (year <= cutoff50) by50++;
  }

  // Median break-even year among paths that reached it.
  let reachedCount = 0;
  for (let sim = 0; sim < simulations; sim++) {
    const year = matrices.breakEvenYears[sim];
    if (year > 0) {
      intScratch[reachedCount++] = year;
    }
  }
  const medianBreakEvenYear =
    reachedCount > 0 ? medianOfInt32(intScratch, reachedCount, intScratch) : null;
  // medianOfInt32 sorts the first `reachedCount` entries in place, which
  // destroys the collected order — harmless, the scratch is reused.

  const burdenQuantiles = pack(matrices.burden);
  const savingsQuantiles = pack(matrices.savings);
  const balanceQuantiles = pack(matrices.balance);
  const last = horizon - 1;

  return {
    years: Int32Array.from({ length: horizon }, (_, i) => i + 1),
    burdenQuantiles,
    savingsQuantiles,
    balanceQuantiles,
    breakEvenYearCounts,
    neverCount,
    probabilities: {
      y10: by10 / simulations,
      y20: by20 / simulations,
      y30: by30 / simulations,
      y50: by50 / simulations,
    },
    medianBreakEvenYear,
    finalMedianBalance: balanceQuantiles[2 * horizon + last],
    finalMedianBurden: burdenQuantiles[2 * horizon + last],
    finalMedianSavings: savingsQuantiles[2 * horizon + last],
  };
}

/** Unpack a 5×horizon quantile block into named series. */
export function unpackQuantiles(packed: Float64Array, horizon: number): PercentileSeries {
  const slice = (row: number): number[] => Array.from(packed.subarray(row * horizon, (row + 1) * horizon));
  return {
    p5: slice(0),
    p25: slice(1),
    median: slice(2),
    p75: slice(3),
    p95: slice(4),
  };
}

/** Evaluate a sensitivity outcome metric directly from the matrices. */
export function computeMetric(
  matrices: EngineMatrices,
  metric: SensitivityMetric,
  buffers: ExtractionBuffers,
): number {
  const { simulations, horizon } = matrices;
  if (metric === 'finalBalance') {
    copyColumn(matrices.balance, simulations, horizon, horizon - 1, buffers.column);
    buffers.column.sort();
    return bandOfSorted(buffers.column, simulations).median;
  }
  if (metric === 'breakEvenYear') {
    let count = 0;
    const { intScratch } = buffers;
    for (let sim = 0; sim < simulations; sim++) {
      const year = matrices.breakEvenYears[sim];
      intScratch[count++] = year > 0 ? year : horizon + 5;
    }
    return medianOfInt32(intScratch, count, intScratch);
  }
  const cutoff = metric === 'probability30' ? Math.min(30, horizon) : Math.min(50, horizon);
  let hit = 0;
  for (let sim = 0; sim < simulations; sim++) {
    const year = matrices.breakEvenYears[sim];
    if (year > 0 && year <= cutoff) hit++;
  }
  return hit / simulations;
}

/** Run a complete simulation synchronously (used by sensitivity/scenarios). */
export function runSync(
  config: ScenarioConfig,
  matrices: EngineMatrices,
  buffers: ExtractionBuffers,
  seedOffset = 0,
): EngineMatrices {
  const rng = new FastPRNG((config.seed + seedOffset) >>> 0);
  simulateChunk(config, matrices, rng, 0, matrices.simulations);
  return matrices;
}

function sensitivityDelta(key: ParameterKey, base: number): number {
  if (key === 'startingWaterUse' || key === 'savingsPotential') return base * 0.2;
  if (key === 'aiGrowthRate' || key === 'efficiencyImprovement') return 0.02;
  return 0.2;
}

export interface SensitivityPassResult {
  results: SensitivityResult[];
  /** The capped config the passes ran under, for reproducibility. */
  probeConfig: ScenarioConfig;
}

/**
 * One-low/one-high sensitivity across all eight parameters. Each probe is a
 * capped Monte Carlo run with its own deterministic seed offset so probes
 * stay independent yet reproducible.
 */
export function runSensitivityPass(
  config: ScenarioConfig,
  metric: SensitivityMetric,
): SensitivityPassResult {
  const probeConfig: ScenarioConfig = {
    ...config,
    simulations: Math.min(config.simulations, SENSITIVITY_SIM_CAP),
  };
  const horizon = probeConfig.horizon;
  const matrices = allocateMatrices(probeConfig.simulations, horizon);
  const buffers = allocateExtraction(probeConfig.simulations, horizon);

  const baseline = computeMetric(
    runSync(probeConfig, matrices, buffers),
    metric,
    buffers,
  );

  const results: SensitivityResult[] = PARAMETER_KEYS.map((key, index) => {
    const base = config[key];
    const delta = sensitivityDelta(key, base);
    const isVolume = key === 'startingWaterUse' || key === 'savingsPotential';
    const lowValue = Math.max(0, base - delta);
    const highValue = isVolume ? base + delta : Math.min(1, base + delta);
    const seedOffset = index * 17 + 3;

    const low = computeMetric(
      runSync({ ...probeConfig, [key]: lowValue } as ScenarioConfig, matrices, buffers, seedOffset),
      metric,
      buffers,
    );
    const high = computeMetric(
      runSync({ ...probeConfig, [key]: highValue } as ScenarioConfig, matrices, buffers, seedOffset),
      metric,
      buffers,
    );
    return {
      key,
      label: PARAMETER_LABELS[key],
      low,
      high,
      influence: Math.abs(high - low),
      baseline,
    };
  });

  results.sort((a, b) => b.influence - a.influence);
  return { results, probeConfig };
}

export interface ScenarioDefinition {
  name: string;
  color: string;
  description: string;
  derive: (config: ScenarioConfig) => ScenarioConfig;
}

/** The three comparison scenarios rendered side by side. */
export const SCENARIO_DEFINITIONS: ScenarioDefinition[] = [
  {
    name: 'Baseline',
    color: '#12766b',
    description: 'Current slider assumptions, unchanged.',
    derive: (config) => config,
  },
  {
    name: 'Accelerated Savings',
    color: '#c98a2d',
    description: 'Higher adoption, effectiveness, realization, and efficiency.',
    derive: (config) => ({
      ...config,
      adoptionRate: Math.min(1, config.adoptionRate + 0.2),
      interventionEffectiveness: Math.min(1, config.interventionEffectiveness + 0.12),
      realizationFactor: Math.min(1, config.realizationFactor + 0.1),
      efficiencyImprovement: Math.min(0.12, config.efficiencyImprovement + 0.012),
    }),
  },
  {
    name: 'High Growth',
    color: '#b3542e',
    description: 'Faster AI expansion with weaker realized savings.',
    derive: (config) => ({
      ...config,
      aiGrowthRate: Math.min(0.3, config.aiGrowthRate + 0.035),
      adoptionRate: Math.max(0, config.adoptionRate - 0.17),
      realizationFactor: Math.max(0, config.realizationFactor - 0.12),
      attributionFraction: Math.max(0, config.attributionFraction - 0.12),
    }),
  },
];

export interface ScenarioPassOutcome {
  name: string;
  color: string;
  medianBalance: Float64Array;
  probability30: number;
  probability50: number;
  medianBreakEvenYear: number | null;
  finalMedianBalance: number;
  finalMedianBurden: number;
}

/** Run the three comparison scenarios at a capped simulation count. */
export function runScenarioPass(config: ScenarioConfig): ScenarioPassOutcome[] {
  return SCENARIO_DEFINITIONS.map((definition) => {
    const scenarioConfig = sanitizeConfig({
      ...definition.derive(config),
      simulations: Math.min(config.simulations, SCENARIO_SIM_CAP),
    });
    const matrices = allocateMatrices(scenarioConfig.simulations, scenarioConfig.horizon);
    const buffers = allocateExtraction(scenarioConfig.simulations, scenarioConfig.horizon);
    const summary = summarizeMatrices(runSync(scenarioConfig, matrices, buffers), scenarioConfig, buffers);
    return {
      name: definition.name,
      color: definition.color,
      medianBalance: summary.balanceQuantiles.slice(2 * scenarioConfig.horizon, 3 * scenarioConfig.horizon),
      probability30: summary.probabilities.y30,
      probability50: summary.probabilities.y50,
      medianBreakEvenYear: summary.medianBreakEvenYear,
      finalMedianBalance: summary.finalMedianBalance,
      finalMedianBurden: summary.finalMedianBurden,
    };
  });
}

/** One-click preset scenarios for the control panel. */
export interface ScenarioPreset {
  id: string;
  name: string;
  note: string;
  values: Partial<Record<ParameterKey, number>>;
}

export const SCENARIO_PRESETS: ScenarioPreset[] = [
  {
    id: 'reference',
    name: 'Reference Case',
    note: 'Illustrative central assumptions.',
    values: {
      startingWaterUse: DEFAULT_CONFIG.startingWaterUse,
      aiGrowthRate: DEFAULT_CONFIG.aiGrowthRate,
      efficiencyImprovement: DEFAULT_CONFIG.efficiencyImprovement,
      savingsPotential: DEFAULT_CONFIG.savingsPotential,
      interventionEffectiveness: DEFAULT_CONFIG.interventionEffectiveness,
      adoptionRate: DEFAULT_CONFIG.adoptionRate,
      realizationFactor: DEFAULT_CONFIG.realizationFactor,
      attributionFraction: DEFAULT_CONFIG.attributionFraction,
    },
  },
  {
    id: 'high-burden',
    name: 'High AI Burden',
    note: 'Faster growth from a larger base, slower efficiency gains.',
    values: {
      startingWaterUse: 232,
      aiGrowthRate: 0.09,
      efficiencyImprovement: 0.022,
      attributionFraction: 0.48,
    },
  },
  {
    id: 'aggressive-conservation',
    name: 'Aggressive Conservation',
    note: 'Larger potential, stronger uptake and realization.',
    values: {
      savingsPotential: 1900,
      interventionEffectiveness: 0.77,
      adoptionRate: 0.76,
      realizationFactor: 0.76,
      efficiencyImprovement: 0.042,
    },
  },
  {
    id: 'delayed-adoption',
    name: 'Delayed Adoption',
    note: 'Same potential, slower and weaker uptake.',
    values: {
      interventionEffectiveness: 0.55,
      adoptionRate: 0.36,
      realizationFactor: 0.54,
    },
  },
];
