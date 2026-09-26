import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  ArrowDownRight,
  Beaker,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  Download,
  Droplets,
  Info,
  Play,
  RotateCcw,
  SlidersHorizontal,
  Waves,
} from 'lucide-react';
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import {
  calculateSensitivity,
  CONFIG_LIMITS,
  DEFAULT_CONFIG,
  runMonteCarlo,
  runScenarioComparison,
  type OutcomeMetric,
  type ScenarioConfig,
  type SimulationResult,
} from '@/simulation';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';

const queryClient = new QueryClient();

type ChartPoint = {
  year: number;
  burden: number;
  burdenLower: number;
  burdenUpper: number;
  savings: number;
  savingsLower: number;
  savingsUpper: number;
  net: number;
  netLower: number;
  netUpper: number;
  netWideLower: number;
  netWideUpper: number;
};

type ComparisonResult = Awaited<ReturnType<typeof runScenarioComparison>>;

const COLORS = {
  burden: 'hsl(24 67% 53%)',
  savings: 'hsl(190 61% 31%)',
  net: 'hsl(43 75% 48%)',
  grid: 'hsl(39 18% 82% / .7)',
  text: 'hsl(195 14% 42%)',
  paper: 'hsl(45 35% 98%)',
};

function formatWater(value: number) {
  const absolute = Math.abs(value);
  if (absolute >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return value.toFixed(0);
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function chartData(result: SimulationResult): ChartPoint[] {
  return result.years.map((year, index) => ({
    year,
    burden: result.burden.median[index] ?? 0,
    burdenLower: result.burden.lower[index] ?? 0,
    burdenUpper: result.burden.upper[index] ?? 0,
    savings: result.savings.median[index] ?? 0,
    savingsLower: result.savings.lower[index] ?? 0,
    savingsUpper: result.savings.upper[index] ?? 0,
    net: result.balance.median[index] ?? 0,
    netLower: result.balance.lower[index] ?? 0,
    netUpper: result.balance.upper[index] ?? 0,
    netWideLower: result.balance.wideLower[index] ?? 0,
    netWideUpper: result.balance.wideUpper[index] ?? 0,
  }));
}

function distributionData(result: SimulationResult) {
  const bins = [
    { range: '1–10', count: 0 },
    { range: '11–20', count: 0 },
    { range: '21–30', count: 0 },
    { range: '31–50', count: 0 },
    { range: '51+', count: 0 },
    { range: 'Never', count: 0 },
  ];
  for (const year of result.breakEvenYears) {
    if (year === null) bins[5].count += 1;
    else if (year <= 10) bins[0].count += 1;
    else if (year <= 20) bins[1].count += 1;
    else if (year <= 30) bins[2].count += 1;
    else if (year <= 50) bins[3].count += 1;
    else bins[4].count += 1;
  }
  return bins;
}

function medianCrossing(result: SimulationResult) {
  const data = chartData(result);
  for (let index = 0; index < data.length; index += 1) {
    if (data[index].net >= 0 && data.slice(index).every((point) => point.net >= 0)) {
      return data[index].year;
    }
  }
  return null;
}

function downloadFile(content: string, filename: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportJSON(result: SimulationResult) {
  downloadFile(JSON.stringify(result, null, 2), 'ai-water-break-even-simulation.json', 'application/json');
}

function exportCSV(result: SimulationResult) {
  const rows = [
    ['year', 'median_cumulative_burden_million_m3', 'median_cumulative_savings_million_m3', 'median_net_balance_million_m3', 'net_middle_50_lower', 'net_middle_50_upper'],
    ...chartData(result).map((point) => [
      point.year,
      point.burden.toFixed(4),
      point.savings.toFixed(4),
      point.net.toFixed(4),
      point.netLower.toFixed(4),
      point.netUpper.toFixed(4),
    ]),
  ];
  downloadFile(rows.map((row) => row.join(',')).join('\n'), 'ai-water-break-even-series.csv', 'text/csv');
}

function downloadChartPNG() {
  const svg = document.querySelector<SVGElement>('[data-testid="chart-cumulative-balance"] svg');
  if (!svg) return;
  const serialized = new XMLSerializer().serializeToString(svg);
  const image = new Image();
  const url = URL.createObjectURL(new Blob([serialized], { type: 'image/svg+xml;charset=utf-8' }));
  image.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1000, svg.clientWidth * 2);
    canvas.height = Math.max(620, svg.clientHeight * 2);
    const context = canvas.getContext('2d');
    if (!context) return;
    context.fillStyle = COLORS.paper;
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) downloadFileFromBlob(blob, 'ai-water-break-even-chart.png');
    }, 'image/png');
    URL.revokeObjectURL(url);
  };
  image.src = url;
}

function downloadFileFromBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function Header() {
  return (
    <header className="sticky top-0 z-30 border-b hairline bg-[hsl(var(--background)/.94)] backdrop-blur-md">
      <div className="mx-auto flex max-w-[1440px] items-center justify-between px-5 py-3 lg:px-10">
        <button data-testid="button-brand-home" onClick={() => scrollToSection('overview')} className="flex items-center gap-3 text-left">
          <span className="flex h-8 w-8 items-center justify-center border border-[hsl(var(--primary)/.4)] bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]">
            <Droplets size={16} strokeWidth={1.7} />
          </span>
          <span>
            <span className="block text-sm font-semibold tracking-[-.02em]">AI Water Break-Even</span>
            <span className="mono block text-[9px] uppercase tracking-[.14em] text-[hsl(var(--muted-foreground))]">Standalone demonstration</span>
          </span>
        </button>
        <nav className="hidden items-center gap-6 text-[11px] font-semibold uppercase tracking-[.12em] text-[hsl(var(--muted-foreground))] md:flex">
          <button onClick={() => scrollToSection('overview')} className="transition-colors hover:text-[hsl(var(--primary))]">Question</button>
          <button onClick={() => scrollToSection('result')} className="transition-colors hover:text-[hsl(var(--primary))]">Result</button>
          <button onClick={() => scrollToSection('assumptions')} className="transition-colors hover:text-[hsl(var(--primary))]">Assumptions</button>
          <button onClick={() => scrollToSection('method')} className="transition-colors hover:text-[hsl(var(--primary))]">Method</button>
        </nav>
        <div className="mono flex items-center gap-2 text-[10px] uppercase tracking-[.1em] text-[hsl(var(--muted-foreground))]">
          <span className="h-1.5 w-1.5 bg-[hsl(var(--accent))]" />
          Seeded run
        </div>
      </div>
    </header>
  );
}

function SliderControl({
  label,
  hint,
  value,
  min,
  max,
  step,
  display,
  onChange,
  testId,
}: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  onChange: (value: number) => void;
  testId: string;
}) {
  return (
    <label className="block border-b hairline pb-4 pt-4 first:pt-0">
      <div className="mb-2 flex items-start justify-between gap-3">
        <span>
          <span className="block text-[12px] font-semibold">{label}</span>
          <span className="mt-0.5 block text-[10px] leading-4 text-[hsl(var(--muted-foreground))]">{hint}</span>
        </span>
        <span className="mono whitespace-nowrap text-[12px] font-medium text-[hsl(var(--primary))]">{display}</span>
      </div>
      <input data-testid={testId} aria-label={label} type="range" value={value} min={min} max={max} step={step} onChange={(event) => onChange(Number(event.target.value))} className="control-range h-1 w-full cursor-pointer appearance-none bg-transparent" />
      <div className="mono mt-1 flex justify-between text-[9px] text-[hsl(var(--muted-foreground))]"><span>{min}</span><span>{max}</span></div>
    </label>
  );
}

function ControlPanel({
  config,
  setConfig,
  onRun,
  onReset,
  onRandomize,
  isRunning,
  progress,
}: {
  config: ScenarioConfig;
  setConfig: (config: ScenarioConfig) => void;
  onRun: () => void;
  onReset: () => void;
  onRandomize: () => void;
  isRunning: boolean;
  progress: number;
}) {
  const update = <K extends keyof ScenarioConfig>(key: K, value: ScenarioConfig[K]) => setConfig({ ...config, [key]: value });
  return (
    <aside id="assumptions" className="section-anchor border border-[hsl(var(--border))] bg-[hsl(var(--card))]">
      <div className="border-b hairline bg-[hsl(var(--primary)/.045)] px-5 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={15} className="text-[hsl(var(--accent))]" />
            <h2 className="text-sm font-semibold">Scenario controls</h2>
          </div>
          <span className="mono text-[9px] uppercase tracking-[.12em] text-[hsl(var(--muted-foreground))]">Inputs</span>
        </div>
        <p className="mt-2 max-w-xs text-[11px] leading-4 text-[hsl(var(--muted-foreground))]">These are user-adjustable, illustrative demo assumptions—not measured inputs.</p>
      </div>
      <div className="px-5">
        <SliderControl label="Starting AI water use" hint="Annual operational water burden at year zero" value={config.startingWaterUse} min={CONFIG_LIMITS.startingWaterUse.min} max={CONFIG_LIMITS.startingWaterUse.max} step={CONFIG_LIMITS.startingWaterUse.step} display={`${config.startingWaterUse}M m³/y`} onChange={(value) => update('startingWaterUse', value)} testId="input-starting-water-use" />
        <SliderControl label="AI growth rate" hint="Annual growth before efficiency improvements" value={config.aiGrowthRate * 100} min={0} max={20} step={0.5} display={`${(config.aiGrowthRate * 100).toFixed(1)}%`} onChange={(value) => update('aiGrowthRate', value / 100)} testId="input-ai-growth" />
        <SliderControl label="Water-efficiency improvement" hint="Annual reduction in water intensity" value={config.efficiencyImprovement * 100} min={0} max={8} step={0.2} display={`${(config.efficiencyImprovement * 100).toFixed(1)}%/y`} onChange={(value) => update('efficiencyImprovement', value / 100)} testId="input-efficiency-improvement" />
        <SliderControl label="Annual savings potential" hint="Water that could be saved before adoption and crediting" value={config.savingsPotential} min={0} max={2000} step={10} display={`${config.savingsPotential}M m³/y`} onChange={(value) => update('savingsPotential', value)} testId="input-savings-potential" />
        <SliderControl label="Intervention effectiveness" hint="How well the intervention works when used" value={config.interventionEffectiveness * 100} min={0} max={100} step={1} display={`${Math.round(config.interventionEffectiveness * 100)}%`} onChange={(value) => update('interventionEffectiveness', value / 100)} testId="input-effectiveness" />
        <SliderControl label="Adoption rate" hint="How much of the potential intervention is actually used" value={config.adoptionRate * 100} min={0} max={100} step={1} display={`${Math.round(config.adoptionRate * 100)}%`} onChange={(value) => update('adoptionRate', value / 100)} testId="input-adoption" />
        <SliderControl label="Realization factor" hint="Share of theoretical savings that becomes realized" value={config.realizationFactor * 100} min={0} max={100} step={1} display={`${Math.round(config.realizationFactor * 100)}%`} onChange={(value) => update('realizationFactor', value / 100)} testId="input-realization" />
        <SliderControl label="AI attribution" hint="Share of realized savings credited to AI-enabled action" value={config.attributionFraction * 100} min={0} max={100} step={1} display={`${Math.round(config.attributionFraction * 100)}%`} onChange={(value) => update('attributionFraction', value / 100)} testId="input-attribution" />
      </div>
      <div className="border-t hairline px-5 py-4">
        <div className="mb-3 flex items-center gap-2">
          <span className="mono text-[9px] uppercase tracking-[.12em] text-[hsl(var(--muted-foreground))]">Simulation settings</span>
        </div>
        <SliderControl label="Time horizon" hint="Years included in each simulated path" value={config.horizon} min={10} max={80} step={1} display={`${config.horizon} years`} onChange={(value) => update('horizon', value)} testId="input-horizon" />
        <SliderControl label="Monte Carlo runs" hint="More runs make percentages more stable" value={config.simulations} min={250} max={20000} step={250} display={config.simulations.toLocaleString()} onChange={(value) => update('simulations', value)} testId="input-simulations" />
        <label className="block pt-4">
          <span className="block text-[12px] font-semibold">Random seed</span>
          <span className="mt-0.5 block text-[10px] leading-4 text-[hsl(var(--muted-foreground))]">Same seed + same assumptions = same result.</span>
          <input data-testid="input-seed" aria-label="Random seed" type="number" min={1} max={999999999} value={config.seed} onChange={(event) => update('seed', Number(event.target.value) || 1)} className="mono mt-2 w-full border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-3 py-2 text-xs outline-none focus:border-[hsl(var(--primary))]" />
        </label>
      </div>
      <div className="p-5 pt-4">
        <button data-testid="button-run-simulation" onClick={onRun} disabled={isRunning} className="flex w-full items-center justify-center gap-2 bg-[hsl(var(--primary))] px-4 py-3 text-xs font-semibold text-[hsl(var(--primary-foreground))] transition-colors hover:bg-[hsl(190 61% 25%)] disabled:cursor-wait disabled:opacity-75 active:translate-y-px">
          <Play size={14} fill="currentColor" /> {isRunning ? `Computing ${progress}%` : 'Run simulation'}
        </button>
        {isRunning && <div className="mt-3 h-1 overflow-hidden bg-[hsl(var(--border))]"><div className="h-full bg-[hsl(var(--accent))] transition-[width]" style={{ width: `${progress}%` }} /></div>}
        <div className="mt-3 flex items-start gap-2 text-[10px] leading-4 text-[hsl(var(--muted-foreground))]">
          <Info size={13} className="mt-0.5 shrink-0 text-[hsl(var(--accent))]" />
          <span>The run samples uncertain values, simulates each year, and aggregates the resulting paths. It is not a preset animation.</span>
        </div>
        {config.simulations < 1_000 && <p className="mt-3 border-l-2 border-[hsl(var(--accent))] pl-2 text-[10px] leading-4 text-[hsl(var(--accent))]">Low simulation count: results may be noisy.</p>}
        <div className="mt-4 flex gap-3 border-t hairline pt-3">
          <button onClick={onReset} className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--primary))]"><RotateCcw size={12} /> Reset</button>
          <button onClick={onRandomize} className="text-[10px] font-semibold text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--primary))]">Randomize scenario</button>
        </div>
      </div>
    </aside>
  );
}

function Legend({ color, children, dashed = false }: { color: string; children: string; dashed?: boolean }) {
  return <span className="inline-flex items-center gap-2 text-[10px] text-[hsl(var(--muted-foreground))]"><i className={`h-2 w-5 ${dashed ? 'border-t border-dashed' : 'h-1'}`} style={{ backgroundColor: dashed ? 'transparent' : color, borderColor: color }} />{children}</span>;
}

function MainChart({ result }: { result: SimulationResult }) {
  const data = chartData(result);
  const crossing = medianCrossing(result);
  return (
    <div className="chart-reveal h-[360px] w-full" data-testid="chart-cumulative-balance">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 12, left: -12, bottom: 6 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 10 }} tickFormatter={(year) => `Y${year}`} />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 10 }} tickFormatter={(value) => `${formatWater(value)}`} width={48} />
          <Tooltip cursor={{ stroke: 'hsl(190 61% 31% / .2)' }} contentStyle={{ border: '1px solid hsl(39 18% 82%)', borderRadius: 2, background: COLORS.paper, fontSize: 11 }} formatter={(value: number, name: string) => [`${formatWater(value)}M m³`, name === 'burden' ? 'Cumulative burden · median' : name === 'savings' ? 'Cumulative savings · median' : 'Net balance · median']} labelFormatter={(label) => `Year ${label}`} />
          <ReferenceLine y={0} stroke="hsl(195 14% 42% / .8)" strokeDasharray="4 4" label={{ value: 'BREAK-EVEN', position: 'insideTopLeft', fill: COLORS.text, fontSize: 9 }} />
          <Area isAnimationActive={false} type="monotone" dataKey="netWideUpper" stroke="none" fill="hsl(43 75% 48% / .07)" />
          <Area isAnimationActive={false} type="monotone" dataKey="netWideLower" stroke="none" fill={COLORS.paper} />
          <Area isAnimationActive={false} type="monotone" dataKey="netUpper" stroke="none" fill="hsl(43 75% 48% / .16)" />
          <Area isAnimationActive={false} type="monotone" dataKey="netLower" stroke="none" fill={COLORS.paper} />
          <Line isAnimationActive={false} type="monotone" dataKey="burden" stroke={COLORS.burden} strokeWidth={2.4} dot={false} />
          <Line isAnimationActive={false} type="monotone" dataKey="savings" stroke={COLORS.savings} strokeWidth={2.4} dot={false} />
          <Line isAnimationActive={false} type="monotone" dataKey="net" stroke={COLORS.net} strokeWidth={1.6} strokeDasharray="5 4" dot={false} />
          {crossing !== null && <ReferenceLine x={crossing} stroke={COLORS.net} strokeDasharray="3 3" label={{ value: `Sustained break-even · Y${crossing}`, position: 'insideTopRight', fill: COLORS.net, fontSize: 9 }} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function ProbabilityCards({ result }: { result: SimulationResult }) {
  return (
    <div className="grid border border-[hsl(var(--border))] bg-[hsl(var(--card))] sm:grid-cols-5">
      {([10, 20, 30, 50] as const).map((year, index) => (
        <div key={year} className={`border-b hairline p-4 sm:border-b-0 ${index < 4 ? 'sm:border-r' : ''}`}>
          <span className="eyebrow">Break-even by</span>
          <div className="mono mt-2 text-2xl font-medium text-[hsl(var(--primary))]">{formatPercent(result.probabilities[year])}</div>
          <p className="mt-1 text-[10px] text-[hsl(var(--muted-foreground))]">{year} years</p>
        </div>
      ))}
      <div className="p-4 sm:col-span-5 sm:border-t sm:border-[hsl(var(--border))]">
        <div className="flex items-baseline justify-between gap-3">
          <span className="eyebrow">Never reached sustained break-even</span>
          <span className="mono text-2xl font-medium text-[hsl(var(--accent))]">{formatPercent(result.neverProbability)}</span>
        </div>
      </div>
    </div>
  );
}

function ResultSummary({ result }: { result: SimulationResult }) {
  const crossing = medianCrossing(result);
  return (
    <section id="result" className="section-anchor">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="eyebrow">Illustrative simulation result</span>
          <h2 className="serif mt-1 text-[2rem] leading-none text-[hsl(var(--primary))] sm:text-[2.45rem]">What happened across the runs?</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => exportCSV(result)} className="inline-flex items-center gap-1.5 border border-[hsl(var(--border))] px-3 py-2 text-[10px] font-semibold hover:border-[hsl(var(--primary))]"><Download size={12} /> CSV</button>
          <button onClick={() => exportJSON(result)} className="inline-flex items-center gap-1.5 border border-[hsl(var(--border))] px-3 py-2 text-[10px] font-semibold hover:border-[hsl(var(--primary))]"><Download size={12} /> JSON</button>
        </div>
      </div>
      <div className="grid border border-[hsl(var(--border))] bg-[hsl(var(--card))] lg:grid-cols-[1.4fr_1fr_1fr]">
        <div className="border-b hairline p-5 lg:border-b-0 lg:border-r">
          <span className="eyebrow">Probability of sustained break-even by 30 years</span>
          <div data-testid="text-break-even-probability" className="metric-number mt-2 text-6xl font-semibold text-[hsl(var(--primary))]">{formatPercent(result.probabilities[30])}</div>
          <p className="mt-2 max-w-sm text-[11px] leading-4 text-[hsl(var(--muted-foreground))]">Across the simulated scenarios. This is a calculated share of runs, not a prediction.</p>
        </div>
        <div className="border-b hairline p-5 lg:border-b-0 lg:border-r">
          <span className="eyebrow">Median sustained crossing</span>
          <div data-testid="text-break-even-year" className="metric-number mt-3 text-4xl font-semibold text-[hsl(var(--primary))]">{result.medianBreakEvenYear ? `Year ${result.medianBreakEvenYear}` : 'Not reached'}</div>
          <p className="mt-2 text-[11px] leading-4 text-[hsl(var(--muted-foreground))]">{result.medianBreakEvenYear ? 'Among simulated paths that stayed at or above zero afterward.' : 'No median path stayed above zero within this horizon.'}</p>
        </div>
        <div className="p-5">
          <span className="eyebrow">Median final net balance</span>
          <div data-testid="text-final-balance" className={`metric-number mt-3 text-4xl font-semibold ${result.finalMedianBalance >= 0 ? 'text-[hsl(var(--primary))]' : 'text-[hsl(var(--accent))]'}`}>{formatWater(result.finalMedianBalance)} <span className="text-xl">M m³</span></div>
          <p className="mt-2 text-[11px] leading-4 text-[hsl(var(--muted-foreground))]">Savings minus burden at the end of the selected horizon.</p>
        </div>
      </div>
      <div className="mt-4 border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 sm:p-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Cumulative AI water burden vs. cumulative AI-enabled savings</h3>
            <p className="mt-1 text-[11px] leading-4 text-[hsl(var(--muted-foreground))]">Net cumulative water balance = savings − burden. Positive values mean the credited savings exceed the simulated AI water burden.</p>
          </div>
          <div className="flex flex-wrap gap-4">
            <Legend color={COLORS.burden}>Burden · median</Legend>
            <Legend color={COLORS.savings}>Savings · median</Legend>
            <Legend color={COLORS.net} dashed>Net balance · median</Legend>
          </div>
        </div>
        <MainChart result={result} />
        <div className="flex flex-wrap items-center justify-between gap-3 border-t hairline pt-3 text-[10px] text-[hsl(var(--muted-foreground))]">
          <span className="flex items-center gap-2"><CircleHelp size={13} className="text-[hsl(var(--accent))]" /> Inner shade = middle 50% · outer shade = middle 90% of net-balance simulations.</span>
          <button onClick={downloadChartPNG} className="inline-flex items-center gap-1.5 font-semibold hover:text-[hsl(var(--primary))]"><Download size={12} /> Download chart PNG</button>
        </div>
        {crossing === null && <p className="mt-3 border-l-2 border-[hsl(var(--accent))] pl-3 text-[11px] font-semibold text-[hsl(var(--accent))]">No sustained break-even within the selected horizon.</p>}
        {crossing !== null && <p className="mt-3 border-l-2 border-[hsl(var(--primary))] pl-3 text-[11px] font-semibold text-[hsl(var(--primary))]">Median path reaches sustained break-even around year {crossing} and remains at or above zero through the selected horizon.</p>}
      </div>
      <div className="mt-4">
        <ProbabilityCards result={result} />
      </div>
    </section>
  );
}

function ComparisonSection({
  comparisons,
  onChooseScenario,
}: {
  comparisons: ComparisonResult;
  onChooseScenario: (index: number) => void;
}) {
  const data = useMemo(() => {
    const horizon = Math.max(...comparisons.map((scenario) => scenario.result.config.horizon));
    return Array.from({ length: horizon }, (_, index) => {
      const point: Record<string, number> = { year: index + 1 };
      for (const scenario of comparisons) point[scenario.name] = scenario.result.balance.median[index] ?? 0;
      return point;
    });
  }, [comparisons]);
  return (
    <section className="section-anchor mt-10" id="comparison">
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <span className="eyebrow">Illustrative scenarios</span>
          <h2 className="serif mt-1 text-[2rem] leading-none text-[hsl(var(--primary))]">What changes the answer?</h2>
        </div>
        <p className="hidden max-w-xs text-right text-[11px] leading-4 text-[hsl(var(--muted-foreground))] sm:block">Three scenario cases use the same model with different assumptions.</p>
      </div>
      <div className="border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 sm:p-6">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold">Median net balance by scenario</h3>
            <p className="mt-1 text-[11px] text-[hsl(var(--muted-foreground))]">Positive means cumulative credited savings exceed cumulative AI water burden.</p>
          </div>
          <div className="flex flex-wrap gap-4">
            {comparisons.map((scenario) => <Legend key={scenario.name} color={scenario.color}>{scenario.name}</Legend>)}
          </div>
        </div>
        <div className="h-[250px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 12, right: 8, left: -12, bottom: 4 }}>
              <CartesianGrid stroke={COLORS.grid} vertical={false} />
              <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 10 }} tickFormatter={(year) => `Y${year}`} />
              <YAxis tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 10 }} tickFormatter={(value) => formatWater(value)} width={45} />
              <Tooltip contentStyle={{ border: '1px solid hsl(39 18% 82%)', borderRadius: 2, background: COLORS.paper, fontSize: 11 }} formatter={(value: number, name: string) => [`${formatWater(value)}M m³`, name]} labelFormatter={(label) => `Year ${label}`} />
              <ReferenceLine y={0} stroke="hsl(195 14% 42% / .8)" strokeDasharray="4 4" />
              {comparisons.map((scenario) => <Line isAnimationActive={false} key={scenario.name} type="monotone" dataKey={scenario.name} stroke={scenario.color} strokeWidth={2.2} dot={false} />)}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="grid border-x border-b hairline bg-[hsl(var(--card))] md:grid-cols-3">
        {comparisons.map((scenario, index) => (
          <button key={scenario.name} onClick={() => onChooseScenario(index)} className={`border-b hairline p-5 text-left transition-colors hover:bg-[hsl(var(--primary)/.05)] md:border-b-0 ${index < 2 ? 'md:border-r' : ''}`}>
            <div className="mb-5 flex items-center justify-between"><span className="mono text-[10px] text-[hsl(var(--muted-foreground))]">0{index + 1}</span><span className="h-2 w-2" style={{ backgroundColor: scenario.color }} /></div>
            <h3 className="text-sm font-semibold">{scenario.name}</h3>
            <p className="mt-2 text-[11px] leading-4 text-[hsl(var(--muted-foreground))]">{index === 0 ? 'Current illustrative assumptions.' : index === 1 ? 'Higher adoption, effectiveness, realization, and efficiency.' : 'Higher AI growth and lower realized, attributable savings.'}</p>
            <div className="mono mt-5 text-[10px] text-[hsl(var(--primary))]">{formatPercent(scenario.result.probabilities[30])} by Y30 · {scenario.result.medianBreakEvenYear ? `median Y${scenario.result.medianBreakEvenYear}` : 'never at median'}</div>
          </button>
        ))}
      </div>
    </section>
  );
}

function DistributionChart({ result }: { result: SimulationResult }) {
  return (
    <div className="h-[220px] w-full" data-testid="chart-break-even-distribution">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={distributionData(result)} margin={{ top: 4, right: 4, left: -24, bottom: 2 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="range" tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 10 }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 10 }} />
          <Tooltip cursor={{ fill: 'hsl(190 61% 31% / .06)' }} contentStyle={{ border: '1px solid hsl(39 18% 82%)', borderRadius: 2, background: COLORS.paper, fontSize: 11 }} formatter={(value: number) => [`${value.toLocaleString()} runs`, 'Simulations']} />
          <Bar isAnimationActive={false} dataKey="count" fill={COLORS.savings} barSize={34} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SensitivityChart({ sensitivity }: { sensitivity: ReturnType<typeof calculateSensitivity> }) {
  const max = Math.max(...sensitivity.map((item) => item.influence), 1);
  const data = sensitivity.map((item) => ({ ...item, influencePercent: (item.influence / max) * 100 }));
  return (
    <div className="h-[250px] w-full" data-testid="chart-sensitivity">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart layout="vertical" data={data} margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={COLORS.grid} horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 9 }} unit="%" />
          <YAxis type="category" dataKey="label" width={132} tickLine={false} axisLine={false} tick={{ fill: 'hsl(194 38% 17%)', fontSize: 10 }} />
          <Tooltip cursor={{ fill: 'hsl(190 61% 31% / .05)' }} contentStyle={{ border: '1px solid hsl(39 18% 82%)', borderRadius: 2, background: COLORS.paper, fontSize: 11 }} formatter={(value: number, name: string, item) => [name === 'influencePercent' ? `${value.toFixed(0)}% relative range` : value, item.payload.label]} />
          <Bar isAnimationActive={false} dataKey="influencePercent" fill={COLORS.burden} barSize={13} radius={[0, 2, 2, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SecondaryAnalysis({ result, config }: { result: SimulationResult; config: ScenarioConfig }) {
  const [metric, setMetric] = useState<OutcomeMetric>('finalBalance');
  const sensitivity = useMemo(() => calculateSensitivity(config, metric), [config, metric]);
  return (
    <section className="mt-10 grid gap-4 lg:grid-cols-[1fr_1.15fr]">
      <div className="border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 sm:p-6">
        <div className="mb-4">
          <span className="eyebrow">Break-even distribution</span>
          <h2 className="serif mt-1 text-2xl text-[hsl(var(--primary))]">When did paths reach sustained break-even?</h2>
          <p className="mt-1 text-[11px] leading-4 text-[hsl(var(--muted-foreground))]">Each bar is a group of Monte Carlo runs. “Never” is counted explicitly.</p>
        </div>
        <DistributionChart result={result} />
      </div>
      <div className="border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-5 sm:p-6">
        <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <span className="eyebrow">Actual influence from reruns</span>
            <h2 className="serif mt-1 text-2xl text-[hsl(var(--primary))]">Which assumptions matter most?</h2>
          </div>
          <select value={metric} onChange={(event) => setMetric(event.target.value as OutcomeMetric)} className="border border-[hsl(var(--input))] bg-[hsl(var(--background))] px-2 py-1.5 text-[10px] outline-none focus:border-[hsl(var(--primary))]">
            <option value="finalBalance">Final net balance</option>
            <option value="probability30">Break-even by 30 years</option>
            <option value="probability50">Break-even by 50 years</option>
            <option value="breakEvenYear">Median break-even year</option>
          </select>
        </div>
        <p className="mt-1 text-[11px] leading-4 text-[hsl(var(--muted-foreground))]">The ranking is calculated by rerunning lower and higher values for each assumption, not hard-coded.</p>
        <SensitivityChart sensitivity={sensitivity} />
        <div className="mt-1 flex items-center gap-2 text-[10px] text-[hsl(var(--muted-foreground))]"><ArrowDownRight size={13} className="text-[hsl(var(--accent))]" /> Longer bars mean a bigger modeled change in the selected outcome.</div>
      </div>
    </section>
  );
}

function MethodSection({ result, config }: { result: SimulationResult; config: ScenarioConfig }) {
  const [open, setOpen] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  return (
    <section className="mt-10" id="method">
      <div className="border border-[hsl(var(--primary)/.28)] bg-[hsl(var(--primary)/.055)] p-5 sm:p-7">
        <div className="grid gap-7 lg:grid-cols-[.75fr_1.25fr] lg:items-start">
          <div>
            <span className="eyebrow text-[hsl(var(--primary))]">Deterministic explanation</span>
            <h2 className="serif mt-2 text-3xl leading-[.95] text-[hsl(var(--primary))]">Why did this happen?</h2>
            <p className="mt-3 max-w-sm text-xs leading-5 text-[hsl(var(--muted-foreground))]">This plain-language reading is generated from the current simulation output. It does not use an LLM and makes no claim about the world outside this demonstration.</p>
          </div>
          <p data-testid="text-explanation" className="border-l-2 border-[hsl(var(--accent))] pl-4 text-sm leading-6">{result.explanation}</p>
        </div>
      </div>
      <div className="border-x border-b hairline bg-[hsl(var(--card))]">
        <button data-testid="button-toggle-method" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-5 py-4 text-left text-xs font-semibold transition-colors hover:bg-[hsl(var(--primary)/.04)] sm:px-7)">
          <span className="flex items-center gap-2"><Beaker size={14} className="text-[hsl(var(--accent))]" /> Under the hood: how the simulation works</span>
          {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
        {open && (
          <div className="border-t hairline px-5 py-5 sm:px-7">
            <div className="grid gap-3 text-[11px] leading-5 text-[hsl(var(--muted-foreground))] sm:grid-cols-4">
              <div><span className="mono mb-1 block text-[10px] text-[hsl(var(--primary))]">01 · Assumptions</span>We choose uncertain values around the scenario settings.</div>
              <div><span className="mono mb-1 block text-[10px] text-[hsl(var(--primary))]">02 · Simulation</span>Each sampled combination is simulated year by year.</div>
              <div><span className="mono mb-1 block text-[10px] text-[hsl(var(--primary))]">03 · Thousands of paths</span>Every path records burden, savings, and sustained break-even.</div>
              <div><span className="mono mb-1 block text-[10px] text-[hsl(var(--primary))]">04 · Distribution</span>We summarize the ensemble, including the “never” outcome.</div>
            </div>
            <div className="mt-5 border-t hairline pt-4 text-[11px] leading-5 text-[hsl(var(--muted-foreground))]">
              <p><strong className="font-semibold text-[hsl(var(--foreground))]">Sign convention:</strong> net cumulative water balance = cumulative AI-enabled water savings − cumulative AI water burden. Positive means savings exceed burden; zero is break-even; negative means burden still exceeds savings.</p>
              <p className="mt-2"><strong className="font-semibold text-[hsl(var(--foreground))]">Sustained break-even:</strong> a path crosses zero and stays at or above zero for the rest of the selected horizon. A temporary one-year crossing does not count.</p>
            </div>
            <button onClick={() => setAdvanced(!advanced)} className="mt-5 inline-flex items-center gap-2 border-t hairline pt-4 text-[10px] font-semibold uppercase tracking-[.12em] text-[hsl(var(--primary))]">{advanced ? <ChevronUp size={12} /> : <ChevronDown size={12} />} Advanced view</button>
            {advanced && (
              <div className="mt-4 grid gap-3 border-t hairline pt-4 text-[10px] text-[hsl(var(--muted-foreground))] sm:grid-cols-3">
                <div><span className="mono block text-[hsl(var(--primary))]">RUNS</span>{config.simulations.toLocaleString()} seeded simulations</div>
                <div><span className="mono block text-[hsl(var(--primary))]">HORIZON</span>{config.horizon} years</div>
                <div><span className="mono block text-[hsl(var(--primary))]">SEED</span>{config.seed}</div>
                <div><span className="mono block text-[hsl(var(--primary))]">BANDS</span>25th–75th percentile envelope</div>
                <div><span className="mono block text-[hsl(var(--primary))]">MEDIAN</span>50th percentile trajectory</div>
                <div><span className="mono block text-[hsl(var(--primary))]">OUTPUT</span>Derived from the current seeded ensemble</div>
                <div><span className="mono block text-[hsl(var(--primary))]">DISTRIBUTIONS</span>Truncated normal and log-normal draws</div>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function Home() {
  const [config, setConfig] = useState<ScenarioConfig>(DEFAULT_CONFIG);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [comparisons, setComparisons] = useState<ComparisonResult>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [lastRun, setLastRun] = useState('Waiting for first seeded run');
  const [runError, setRunError] = useState<string | null>(null);

  const runSimulation = async (nextConfig: ScenarioConfig, label: string) => {
    setIsRunning(true);
    setProgress(0);
    setRunError(null);
    try {
      const nextResult = await runMonteCarlo(nextConfig, (completed, total) => setProgress(Math.round((completed / total) * 100)));
      setResult(nextResult);
      setComparisons(await runScenarioComparison(nextConfig));
      setLastRun(`${label} · seed ${nextConfig.seed}`);
    } catch (error) {
      setRunError(error instanceof Error ? error.message : 'The simulation could not complete.');
    } finally {
      setIsRunning(false);
    }
  };

  useEffect(() => {
    void runSimulation(DEFAULT_CONFIG, 'Reference case');
  }, []);

  const chooseScenario = (index: number) => {
    const scenarios = comparisons.length ? comparisons : [];
    const selected = scenarios[index]?.result.config;
    if (selected) {
      setConfig(selected);
      void runSimulation(selected, scenarios[index].name);
    }
  };

  const randomizeScenario = () => {
    const nextSeed = ((config.seed * 1103515245 + 12345) % 999999999) || 1;
    const randomized = {
      ...config,
      seed: nextSeed,
      aiGrowthRate: Math.min(0.2, Math.max(0.02, config.aiGrowthRate + (((nextSeed % 11) - 5) / 1000))),
      adoptionRate: Math.min(1, Math.max(0, config.adoptionRate + (((nextSeed % 17) - 8) / 100))),
      realizationFactor: Math.min(1, Math.max(0, config.realizationFactor + (((nextSeed % 13) - 6) / 100))),
    };
    setConfig(randomized);
    void runSimulation(randomized, 'Randomized case');
  };

  return (
    <div className="instrument-page paper-grid">
      <Header />
      <main className="mx-auto max-w-[1440px] px-5 pb-20 lg:px-10">
        <section id="overview" className="section-anchor grid gap-8 pb-12 pt-12 lg:grid-cols-[1.12fr_.88fr] lg:items-end lg:pt-20">
          <div className="fade-rise">
            <div className="mb-5 flex items-center gap-3"><span className="eyebrow">AI Water Break-Even</span><span className="h-px w-12 bg-[hsl(var(--accent))]" /></div>
            <h1 className="serif max-w-3xl text-[3.6rem] leading-[.88] tracking-[-.035em] text-[hsl(var(--primary))] sm:text-[5rem] lg:text-[6.3rem]">Can AI save more water than it <em className="text-[hsl(var(--accent))]">consumes?</em></h1>
            <p className="mt-7 max-w-xl text-sm leading-6 text-[hsl(var(--muted-foreground))]">Explore a seeded Monte Carlo model of one question: under illustrative assumptions, when could cumulative AI-enabled water savings catch up with cumulative AI water burden?</p>
            <div className="mt-7 flex flex-wrap items-center gap-4">
              <button onClick={() => scrollToSection('result')} className="inline-flex items-center gap-2 border-b-2 border-[hsl(var(--accent))] pb-1 text-xs font-semibold text-[hsl(var(--primary))]">Read the current result <ArrowDownRight size={14} /></button>
              <span className="mono text-[10px] uppercase tracking-[.1em] text-[hsl(var(--muted-foreground))]">Not a forecast · not empirical data</span>
            </div>
          </div>
          <div className="fade-rise fade-rise-delay-2 relative border-l-2 border-[hsl(var(--accent)/.65)] pl-5 lg:mb-2 lg:ml-auto lg:max-w-md">
            <span className="eyebrow">How to use this instrument</span>
            <p className="serif mt-3 text-2xl leading-tight text-[hsl(var(--primary))]">Move one assumption. Rerun the world.</p>
            <p className="mt-3 text-xs leading-5 text-[hsl(var(--muted-foreground))]">The chart is the argument: burden and savings accumulate at different rates, while the ensemble keeps uncertainty visible.</p>
          </div>
        </section>

        <div className="grid gap-8 lg:grid-cols-[300px_1fr] lg:items-start">
          <div className="fade-rise fade-rise-delay-1 lg:sticky lg:top-20">
            <ControlPanel config={config} setConfig={setConfig} onRun={() => void runSimulation(config, 'Custom case')} onReset={() => { setConfig(DEFAULT_CONFIG); void runSimulation(DEFAULT_CONFIG, 'Reference case'); }} onRandomize={randomizeScenario} isRunning={isRunning} progress={progress} />
          </div>
          <div className="min-w-0">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b hairline pb-3">
              <span className="mono text-[10px] uppercase tracking-[.12em] text-[hsl(var(--muted-foreground))]">Live readout / {lastRun}</span>
              {isRunning && <span className="mono text-[10px] uppercase tracking-[.12em] text-[hsl(var(--accent))]">Computing ensemble…</span>}
            </div>
            {result ? (
              <>
                {runError && <p className="mb-4 border-l-2 border-[hsl(var(--destructive))] pl-3 text-xs text-[hsl(var(--destructive))]">{runError}</p>}
                <ResultSummary result={result} />
                {comparisons.length > 0 && <ComparisonSection comparisons={comparisons} onChooseScenario={chooseScenario} />}
                <SecondaryAnalysis result={result} config={config} />
                <MethodSection result={result} config={config} />
              </>
            ) : (
              <div className="border border-[hsl(var(--border))] bg-[hsl(var(--card))] p-10 text-center"><p className="serif text-3xl text-[hsl(var(--primary))]">{runError ? 'The run needs another try.' : 'Sampling the first ensemble…'}</p><p className="mt-2 text-xs text-[hsl(var(--muted-foreground))]">{runError ?? 'The result will appear when the calculation finishes.'}</p></div>
            )}
          </div>
        </div>
        <footer className="mt-16 flex flex-col justify-between gap-3 border-t hairline pt-5 text-[10px] leading-4 text-[hsl(var(--muted-foreground))] sm:flex-row">
          <span>This interactive model is a standalone demonstration inspired by the AI Water Break-Even research framework. Its default values are illustrative and are not research findings.</span>
          <span className="mono">Seeded Monte Carlo · illustrative assumptions · not a forecast</span>
        </footer>
      </main>
    </div>
  );
}

function Router() {
  return (
    <RoutedErrorBoundary>
      <Switch>
        <Route path="/" component={Home} />
        <Route component={NotFound} />
      </Switch>
    </RoutedErrorBoundary>
  );
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;