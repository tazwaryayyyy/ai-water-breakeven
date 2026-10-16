/**
 * Strict domain and worker-protocol types for the AI water break-even
 * simulator. Units: all water volumes are millions of cubic meters (M m³);
 * rates and shares are fractions in [0, 1] unless a field name says percent.
 */

/** The eight uncertain model parameters plus run controls. */
export interface ScenarioConfig {
  /** Annual AI operational water use at year zero (M m³/yr). */
  startingWaterUse: number;
  /** Annual growth of AI water demand (fraction/yr, e.g. 0.055 = 5.5%). */
  aiGrowthRate: number;
  /** Annual efficiency improvement of AI water intensity (fraction/yr). */
  efficiencyImprovement: number;
  /** Annual water that interventions could save before realization (M m³/yr). */
  savingsPotential: number;
  /** Share of adopted interventions that actually deliver savings. */
  interventionEffectiveness: number;
  /** Long-run adoption ceiling of water-saving interventions. */
  adoptionRate: number;
  /** Share of theoretical savings realized in practice. */
  realizationFactor: number;
  /** Share of realized savings credited to AI-enabled action. */
  attributionFraction: number;
  /** Simulated years per path (10–80). */
  horizon: number;
  /** Monte Carlo paths (250–20,000). */
  simulations: number;
  /** PRNG seed; same seed + config reproduces the run exactly. */
  seed: number;
}

export type ParameterKey =
  | 'startingWaterUse'
  | 'aiGrowthRate'
  | 'efficiencyImprovement'
  | 'savingsPotential'
  | 'interventionEffectiveness'
  | 'adoptionRate'
  | 'realizationFactor'
  | 'attributionFraction';

export type RunControlKey = 'horizon' | 'simulations' | 'seed';

export type SensitivityMetric = 'finalBalance' | 'probability30' | 'probability50' | 'breakEvenYear';

export interface ParameterLimit {
  min: number;
  max: number;
  step: number;
}

export const PARAMETER_KEYS: readonly ParameterKey[] = [
  'startingWaterUse',
  'aiGrowthRate',
  'efficiencyImprovement',
  'savingsPotential',
  'interventionEffectiveness',
  'adoptionRate',
  'realizationFactor',
  'attributionFraction',
];

export const PARAMETER_LIMITS: Record<ParameterKey | RunControlKey, ParameterLimit> = {
  startingWaterUse: { min: 0, max: 800, step: 5 },
  aiGrowthRate: { min: 0, max: 0.2, step: 0.005 },
  efficiencyImprovement: { min: 0, max: 0.08, step: 0.002 },
  savingsPotential: { min: 0, max: 2000, step: 10 },
  interventionEffectiveness: { min: 0, max: 1, step: 0.01 },
  adoptionRate: { min: 0, max: 1, step: 0.01 },
  realizationFactor: { min: 0, max: 1, step: 0.01 },
  attributionFraction: { min: 0, max: 1, step: 0.01 },
  horizon: { min: 10, max: 80, step: 1 },
  simulations: { min: 250, max: 20000, step: 250 },
  seed: { min: 1, max: 999999999, step: 1 },
};

export const PARAMETER_LABELS: Record<ParameterKey, string> = {
  startingWaterUse: 'Starting AI water use',
  aiGrowthRate: 'AI growth rate',
  efficiencyImprovement: 'Efficiency improvement',
  savingsPotential: 'Savings potential',
  interventionEffectiveness: 'Intervention effectiveness',
  adoptionRate: 'Adoption rate',
  realizationFactor: 'Realization factor',
  attributionFraction: 'AI attribution',
};

export const SENSITIVITY_METRIC_LABELS: Record<SensitivityMetric, string> = {
  finalBalance: 'Final net balance',
  probability30: 'Break-even by year 30',
  probability50: 'Break-even by year 50',
  breakEvenYear: 'Median break-even year',
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
  simulations: 10000,
  seed: 271828,
};

/** Five-statistic percentile envelope for one trajectory curve. */
export interface PercentileSeries {
  p5: number[];
  p25: number[];
  median: number[];
  p75: number[];
  p95: number[];
}

export interface BreakEvenProbabilities {
  y10: number;
  y20: number;
  y30: number;
  y50: number;
}

/** Fully decoded simulation summary, ready for charts and export. */
export interface SimulationSummary {
  config: ScenarioConfig;
  years: number[];
  burden: PercentileSeries;
  savings: PercentileSeries;
  balance: PercentileSeries;
  /** Count of paths whose sustained break-even year is `year`, for 1..horizon. */
  breakEvenCounts: number[];
  /** Count of paths that never reach sustained break-even. */
  neverCount: number;
  probabilities: BreakEvenProbabilities;
  neverProbability: number;
  medianBreakEvenYear: number | null;
  finalMedianBalance: number;
  finalMedianBurden: number;
  finalMedianSavings: number;
}

export interface SensitivityResult {
  key: ParameterKey;
  label: string;
  /** Metric value with the parameter at its low setting. */
  low: number;
  /** Metric value with the parameter at its high setting. */
  high: number;
  /** |high − low|, the tornado bar length. */
  influence: number;
  /** Metric value at the untouched baseline (tornado center line). */
  baseline: number;
}

export interface ScenarioOutcome {
  name: string;
  color: string;
  description: string;
  medianBalance: number[];
  probability30: number;
  probability50: number;
  medianBreakEvenYear: number | null;
  finalMedianBalance: number;
  finalMedianBurden: number;
}

export interface SimulationResult {
  summary: SimulationSummary;
  sensitivity: SensitivityResult[];
  scenarios: ScenarioOutcome[];
  computeMs: number;
}

/* ------------------------------------------------------------------ */
/* Worker wire protocol. Typed-array payloads are transferred, not     */
/* cloned; every message carries the requestId that issued it.         */
/* ------------------------------------------------------------------ */

export type WorkerStage = 'baseline' | 'sensitivity' | 'scenarios';

export interface RunRequestMessage {
  type: 'run';
  requestId: number;
  config: ScenarioConfig;
  includeSensitivity: boolean;
  includeScenarios: boolean;
  sensitivityMetric: SensitivityMetric;
}

export interface CancelRequestMessage {
  type: 'cancel';
  requestId: number;
}

export type WorkerInboundMessage = RunRequestMessage | CancelRequestMessage;

/**
 * Wire form of a simulation summary. Each quantile matrix packs the five
 * statistics row-major as [p5 · horizon | p25 · horizon | median | p75 | p95];
 * buffers are moved to the main thread via the postMessage transfer list.
 */
export interface SummaryWire {
  years: Int32Array;
  burdenQuantiles: Float64Array;
  savingsQuantiles: Float64Array;
  balanceQuantiles: Float64Array;
  breakEvenYearCounts: Int32Array;
  neverCount: number;
  probabilities: BreakEvenProbabilities;
  medianBreakEvenYear: number | null;
  finalMedianBalance: number;
  finalMedianBurden: number;
  finalMedianSavings: number;
}

export interface ResultPayload {
  config: ScenarioConfig;
  summary: SummaryWire;
  sensitivity: SensitivityResult[];
  scenarioOutcomes: Array<Omit<ScenarioOutcome, 'medianBalance' | 'description'> & { medianBalance: Float64Array }>;
  computeMs: number;
}

export interface ProgressMessage {
  type: 'progress';
  requestId: number;
  stage: WorkerStage;
  completed: number;
  total: number;
}

export interface ResultMessage {
  type: 'result';
  requestId: number;
  payload: ResultPayload;
}

export interface ErrorMessage {
  type: 'error';
  requestId: number;
  message: string;
}

export type WorkerOutboundMessage = ProgressMessage | ResultMessage | ErrorMessage;
