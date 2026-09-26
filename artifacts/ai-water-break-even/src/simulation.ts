export type OutcomeMetric =
  | 'finalBalance'
  | 'probability30'
  | 'probability50'
  | 'breakEvenYear';

export type ScenarioConfig = {
  startingWaterUse: number;
  aiGrowthRate: number;
  efficiencyImprovement: number;
  savingsPotential: number;
  interventionEffectiveness: number;
  adoptionRate: number;
  realizationFactor: number;
  attributionFraction: number;
  horizon: number;
  simulations: number;
  seed: number;
};

export type PercentileSeries = {
  median: number[];
  lower: number[];
  upper: number[];
  wideLower: number[];
  wideUpper: number[];
};

export type SimulationRun = {
  burden: number[];
  savings: number[];
  balance: number[];
  breakEvenYear: number | null;
};

export type SimulationResult = {
  config: ScenarioConfig;
  years: number[];
  burden: PercentileSeries;
  savings: PercentileSeries;
  balance: PercentileSeries;
  breakEvenYears: Array<number | null>;
  breakEvenCounts: Record<number | 'never', number>;
  probabilities: Record<10 | 20 | 30 | 50, number>;
  neverProbability: number;
  medianBreakEvenYear: number | null;
  finalMedianBalance: number;
  finalMedianBurden: number;
  finalMedianSavings: number;
  sensitivity: SensitivityResult[];
  explanation: string;
};

export type SensitivityResult = {
  key: keyof Pick<
    ScenarioConfig,
    | 'startingWaterUse'
    | 'aiGrowthRate'
    | 'efficiencyImprovement'
    | 'savingsPotential'
    | 'interventionEffectiveness'
    | 'adoptionRate'
    | 'realizationFactor'
    | 'attributionFraction'
  >;
  label: string;
  low: number;
  high: number;
  influence: number;
};

export const DEFAULT_CONFIG: ScenarioConfig = {
  startingWaterUse: 145,
  aiGrowthRate: 0.055,
  efficiencyImprovement: 0.03,
  savingsPotential: 1500,
  interventionEffectiveness: 0.65,
  adoptionRate: 0.56,
  realizationFactor: 0.66,
  attributionFraction: 0.58,
  horizon: 50,
  simulations: 10_000,
  seed: 271828,
};

export const CONFIG_LIMITS = {
  startingWaterUse: { min: 0, max: 800, step: 5 },
  aiGrowthRate: { min: 0, max: 0.2, step: 0.005 },
  efficiencyImprovement: { min: 0, max: 0.08, step: 0.002 },
  savingsPotential: { min: 0, max: 2_000, step: 10 },
  interventionEffectiveness: { min: 0, max: 1, step: 0.01 },
  adoptionRate: { min: 0, max: 1, step: 0.01 },
  realizationFactor: { min: 0, max: 1, step: 0.01 },
  attributionFraction: { min: 0, max: 1, step: 0.01 },
  horizon: { min: 10, max: 80, step: 1 },
  simulations: { min: 250, max: 20_000, step: 250 },
  seed: { min: 1, max: 999_999_999, step: 1 },
} as const;

const PARAMETER_LABELS: Record<SensitivityResult['key'], string> = {
  startingWaterUse: 'Starting AI water use',
  aiGrowthRate: 'AI growth rate',
  efficiencyImprovement: 'Water-efficiency improvement',
  savingsPotential: 'Annual savings potential',
  interventionEffectiveness: 'Intervention effectiveness',
  adoptionRate: 'Adoption rate',
  realizationFactor: 'Realization factor',
  attributionFraction: 'AI attribution',
};

class SeededRandom {
  private state: number;

  constructor(seed: number) {
    this.state = (Math.floor(Math.abs(seed)) >>> 0) || 1;
  }

  next(): number {
    this.state = (1664525 * this.state + 1013904223) >>> 0;
    return this.state / 4_294_967_296;
  }

  normal(mean = 0, standardDeviation = 1): number {
    const u1 = Math.max(this.next(), Number.EPSILON);
    const u2 = this.next();
    return (
      mean +
      standardDeviation *
        Math.sqrt(-2 * Math.log(u1)) *
        Math.cos(2 * Math.PI * u2)
    );
  }
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value));
}

function positiveLogNormal(random: SeededRandom, value: number, relativeSpread: number) {
  return Math.max(0, value * Math.exp(random.normal(0, relativeSpread)));
}

function quantile(sorted: number[], probability: number): number {
  if (sorted.length === 0) return 0;
  const index = (sorted.length - 1) * probability;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower] ?? 0;
  const weight = index - lower;
  return (sorted[lower] ?? 0) * (1 - weight) + (sorted[upper] ?? 0) * weight;
}

function percentileSeries(runs: SimulationRun[], field: 'burden' | 'savings' | 'balance', horizon: number): PercentileSeries {
  const median: number[] = [];
  const lower: number[] = [];
  const upper: number[] = [];
  const wideLower: number[] = [];
  const wideUpper: number[] = [];

  for (let yearIndex = 0; yearIndex < horizon; yearIndex += 1) {
    const values = runs.map((run) => run[field][yearIndex] ?? 0).sort((a, b) => a - b);
    median.push(quantile(values, 0.5));
    lower.push(quantile(values, 0.25));
    upper.push(quantile(values, 0.75));
    wideLower.push(quantile(values, 0.05));
    wideUpper.push(quantile(values, 0.95));
  }

  return { median, lower, upper, wideLower, wideUpper };
}

function sampleParameters(config: ScenarioConfig, random: SeededRandom) {
  return {
    startingWaterUse: positiveLogNormal(random, config.startingWaterUse, 0.12),
    aiGrowthRate: clamp(random.normal(config.aiGrowthRate, 0.012), 0, 0.3),
    efficiencyImprovement: clamp(
      random.normal(config.efficiencyImprovement, 0.004),
      0,
      0.12,
    ),
    savingsPotential: positiveLogNormal(random, config.savingsPotential, 0.16),
    interventionEffectiveness: clamp(
      random.normal(config.interventionEffectiveness, 0.09),
    ),
    adoptionRate: clamp(random.normal(config.adoptionRate, 0.1)),
    realizationFactor: clamp(random.normal(config.realizationFactor, 0.09)),
    attributionFraction: clamp(random.normal(config.attributionFraction, 0.1)),
  };
}

function simulateOne(config: ScenarioConfig, random: SeededRandom): SimulationRun {
  const sampled = sampleParameters(config, random);
  const burden: number[] = [];
  const savings: number[] = [];
  const balance: number[] = [];
  let cumulativeBurden = 0;
  let cumulativeSavings = 0;

  for (let year = 1; year <= config.horizon; year += 1) {
    const burdenGrowth =
      Math.pow(1 + sampled.aiGrowthRate, year) *
      Math.pow(1 - sampled.efficiencyImprovement, year);
    const annualBurden = sampled.startingWaterUse * burdenGrowth;

    const adoptionCurve = sampled.adoptionRate * (1 - Math.exp(-0.105 * year));
    const potentialGrowth = Math.pow(1.022, year);
    const annualSavings =
      sampled.savingsPotential *
      potentialGrowth *
      adoptionCurve *
      sampled.interventionEffectiveness *
      sampled.realizationFactor *
      sampled.attributionFraction;

    cumulativeBurden += annualBurden;
    cumulativeSavings += annualSavings;
    burden.push(cumulativeBurden);
    savings.push(cumulativeSavings);
    balance.push(cumulativeSavings - cumulativeBurden);
  }

  let breakEvenYear: number | null = null;
  for (let yearIndex = 0; yearIndex < balance.length; yearIndex += 1) {
    if ((balance[yearIndex] ?? -Infinity) >= 0) {
      const staysAtOrAboveZero = balance
        .slice(yearIndex)
        .every((value) => value >= 0);
      if (staysAtOrAboveZero) {
        breakEvenYear = yearIndex + 1;
        break;
      }
    }
  }

  return { burden, savings, balance, breakEvenYear };
}

function buildExplanation(result: Omit<SimulationResult, 'sensitivity' | 'explanation'>, sensitivity: SensitivityResult[]): string {
  const breakEvenShare = 1 - result.neverProbability;
  const dominant = sensitivity[0];
  if (breakEvenShare < 0.1) {
    return `Most simulated paths did not reach sustained break-even within the selected horizon. The median cumulative balance ended ${Math.abs(result.finalMedianBalance).toFixed(0)} million m³ below zero, with ${dominant?.label.toLowerCase() ?? 'the leading assumption'} having the largest influence on that outcome.`;
  }
  if (result.neverProbability < 0.15 && result.medianBreakEvenYear !== null) {
    return `Most simulated paths reached sustained break-even around year ${result.medianBreakEvenYear}. In this scenario, realized savings grow enough to stay ahead of the cumulative AI water burden, led most strongly by ${dominant?.label.toLowerCase() ?? 'the leading assumption'}.`;
  }
  if (result.medianBreakEvenYear !== null) {
    return `Some simulated paths reached sustained break-even around year ${result.medianBreakEvenYear}, while others did not within the selected horizon. The spread comes from uncertainty in the assumptions, especially ${dominant?.label.toLowerCase() ?? 'the leading assumption'}.`;
  }
  return `The simulated paths remained below zero through the selected horizon. That means cumulative AI water burden still exceeded credited water savings under these assumptions; ${dominant?.label.toLowerCase() ?? 'the leading assumption'} mattered most.`;
}

function summarizeBreakEvenYears(breakEvenYears: Array<number | null>, horizon: number) {
  const counts: Record<number | 'never', number> = { never: 0 };
  for (const year of breakEvenYears) {
    if (year === null) {
      counts.never = (counts.never ?? 0) + 1;
    } else {
      counts[year] = (counts[year] ?? 0) + 1;
    }
  }
  const total = breakEvenYears.length || 1;
  const atOrBefore = (cutoff: number) =>
    breakEvenYears.filter((year) => year !== null && year <= Math.min(cutoff, horizon)).length /
    total;
  const reached = breakEvenYears.filter((year): year is number => year !== null).sort((a, b) => a - b);
  return {
    counts,
    probabilities: {
      10: atOrBefore(10),
      20: atOrBefore(20),
      30: atOrBefore(30),
      50: atOrBefore(50),
    } as Record<10 | 20 | 30 | 50, number>,
    neverProbability: (counts.never ?? 0) / total,
    medianBreakEvenYear: reached.length ? Math.round(quantile(reached, 0.5)) : null,
  };
}

function sensitivityFor(
  config: ScenarioConfig,
  key: SensitivityResult['key'],
  seedOffset: number,
): SensitivityResult {
  const lowConfig = { ...config, simulations: Math.min(config.simulations, 1_200), seed: config.seed + seedOffset };
  const highConfig = { ...lowConfig };
  const base = config[key];
  const numericBase = Number(base);
  const delta =
    key === 'startingWaterUse' || key === 'savingsPotential'
      ? numericBase * 0.2
      : key === 'aiGrowthRate' || key === 'efficiencyImprovement'
        ? 0.02
        : 0.2;
  (lowConfig as unknown as Record<string, number>)[key] = Math.max(
    0,
    numericBase - delta,
  );
  (highConfig as unknown as Record<string, number>)[key] = numericBase + delta;
  if (key !== 'startingWaterUse' && key !== 'savingsPotential') {
    (highConfig as unknown as Record<string, number>)[key] = Math.min(
      1,
      highConfig[key] as number,
    );
  }

  const lowRuns = runRuns(lowConfig);
  const highRuns = runRuns(highConfig);
  const lowValue = metricValue(lowRuns, lowConfig.horizon, 'finalBalance');
  const highValue = metricValue(highRuns, highConfig.horizon, 'finalBalance');
  return {
    key,
    label: PARAMETER_LABELS[key],
    low: lowValue,
    high: highValue,
    influence: Math.abs(highValue - lowValue),
  };
}

function runRuns(config: ScenarioConfig): SimulationRun[] {
  const random = new SeededRandom(config.seed);
  const runs: SimulationRun[] = [];
  for (let index = 0; index < config.simulations; index += 1) {
    runs.push(simulateOne(config, random));
  }
  return runs;
}

function metricValue(
  runs: SimulationRun[],
  horizon: number,
  metric: OutcomeMetric,
): number {
  if (metric === 'finalBalance') {
    const values = runs.map((run) => run.balance[horizon - 1] ?? 0).sort((a, b) => a - b);
    return quantile(values, 0.5);
  }
  if (metric === 'breakEvenYear') {
    const values = runs
      .map((run) => run.breakEvenYear ?? horizon + 5)
      .sort((a, b) => a - b);
    return quantile(values, 0.5);
  }
  const year = metric === 'probability30' ? 30 : 50;
  return runs.filter((run) => run.breakEvenYear !== null && run.breakEvenYear <= year).length / (runs.length || 1);
}

export function calculateSensitivity(
  config: ScenarioConfig,
  metric: OutcomeMetric = 'finalBalance',
): SensitivityResult[] {
  const keys: SensitivityResult['key'][] = [
    'startingWaterUse',
    'aiGrowthRate',
    'efficiencyImprovement',
    'savingsPotential',
    'interventionEffectiveness',
    'adoptionRate',
    'realizationFactor',
    'attributionFraction',
  ];
  const results = keys.map((key, index) => {
    if (metric === 'finalBalance') return sensitivityFor(config, key, index * 17 + 3);
    const lowConfig = { ...config, simulations: Math.min(config.simulations, 1_200), seed: config.seed + index * 17 + 3 };
    const highConfig = { ...lowConfig };
    const base = Number(config[key]);
    const delta = key === 'startingWaterUse' || key === 'savingsPotential' ? base * 0.2 : key === 'aiGrowthRate' || key === 'efficiencyImprovement' ? 0.02 : 0.2;
    (lowConfig as unknown as Record<string, number>)[key] = Math.max(0, base - delta);
    (highConfig as unknown as Record<string, number>)[key] = key === 'startingWaterUse' || key === 'savingsPotential' ? base + delta : Math.min(1, base + delta);
    const low = metricValue(runRuns(lowConfig), lowConfig.horizon, metric);
    const high = metricValue(runRuns(highConfig), highConfig.horizon, metric);
    return { key, label: PARAMETER_LABELS[key], low, high, influence: Math.abs(high - low) };
  });
  return results.sort((a, b) => b.influence - a.influence);
}

export async function runMonteCarlo(
  config: ScenarioConfig,
  onProgress?: (completed: number, total: number) => void,
  options?: { includeSensitivity?: boolean },
): Promise<SimulationResult> {
  const safeConfig: ScenarioConfig = {
    ...config,
    horizon: Math.round(clamp(config.horizon, CONFIG_LIMITS.horizon.min, CONFIG_LIMITS.horizon.max)),
    simulations: Math.round(clamp(config.simulations, CONFIG_LIMITS.simulations.min, CONFIG_LIMITS.simulations.max)),
    seed: Math.round(clamp(config.seed, CONFIG_LIMITS.seed.min, CONFIG_LIMITS.seed.max)),
  };
  const random = new SeededRandom(safeConfig.seed);
  const runs: SimulationRun[] = [];

  for (let index = 0; index < safeConfig.simulations; index += 1) {
    runs.push(simulateOne(safeConfig, random));
    if (onProgress && (index % 1_000 === 0 || index === safeConfig.simulations - 1)) {
      onProgress(index + 1, safeConfig.simulations);
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    }
  }

  const breakEvenYears = runs.map((run) => run.breakEvenYear);
  const summary = summarizeBreakEvenYears(breakEvenYears, safeConfig.horizon);
  const burden = percentileSeries(runs, 'burden', safeConfig.horizon);
  const savings = percentileSeries(runs, 'savings', safeConfig.horizon);
  const balance = percentileSeries(runs, 'balance', safeConfig.horizon);
  const withoutComputedFields = {
    config: safeConfig,
    years: Array.from({ length: safeConfig.horizon }, (_, index) => index + 1),
    burden,
    savings,
    balance,
    breakEvenYears,
    breakEvenCounts: summary.counts,
    probabilities: summary.probabilities,
    neverProbability: summary.neverProbability,
    medianBreakEvenYear: summary.medianBreakEvenYear,
    finalMedianBalance: balance.median.at(-1) ?? 0,
    finalMedianBurden: burden.median.at(-1) ?? 0,
    finalMedianSavings: savings.median.at(-1) ?? 0,
  };
  const sensitivity = options?.includeSensitivity === false
    ? []
    : calculateSensitivity(safeConfig);

  return {
    ...withoutComputedFields,
    sensitivity,
    explanation: buildExplanation(withoutComputedFields, sensitivity),
  };
}

export function createScenarioConfigs(config: ScenarioConfig) {
  return [
    { name: 'Baseline', color: '#86d8c5', config },
    {
      name: 'More savings realized',
      color: '#f0bd73',
      config: {
        ...config,
        adoptionRate: Math.min(1, config.adoptionRate + 0.2),
        interventionEffectiveness: Math.min(1, config.interventionEffectiveness + 0.12),
        realizationFactor: Math.min(1, config.realizationFactor + 0.1),
        efficiencyImprovement: Math.min(0.12, config.efficiencyImprovement + 0.012),
      },
    },
    {
      name: 'Difficult conditions',
      color: '#ed8e7c',
      config: {
        ...config,
        aiGrowthRate: Math.min(0.3, config.aiGrowthRate + 0.035),
        adoptionRate: Math.max(0, config.adoptionRate - 0.17),
        realizationFactor: Math.max(0, config.realizationFactor - 0.12),
        attributionFraction: Math.max(0, config.attributionFraction - 0.12),
      },
    },
  ];
}

export async function runScenarioComparison(
  config: ScenarioConfig,
): Promise<Array<{ name: string; color: string; result: SimulationResult }>> {
  const scenarios = createScenarioConfigs(config);
  const results: Array<{ name: string; color: string; result: SimulationResult }> = [];
  for (const scenario of scenarios) {
    results.push({
      name: scenario.name,
      color: scenario.color,
      result: await runMonteCarlo({
        ...scenario.config,
        simulations: Math.min(2_500, scenario.config.simulations),
      }, undefined, { includeSensitivity: false }),
    });
  }
  return results;
}
