import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChevronDown, ChevronUp, Download, RotateCcw } from 'lucide-react';
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
  savings: number;
  net: number;
  netLower: number;
  netUpper: number;
  netWideLower: number;
  netWideUpper: number;
};

type ComparisonResult = Awaited<ReturnType<typeof runScenarioComparison>>;

const COLORS = {
  burden: 'hsl(24 26% 40%)',
  savings: 'hsl(190 45% 29%)',
  net: 'hsl(24 62% 45%)',
  grid: 'hsl(40 11% 82% / .8)',
  text: 'hsl(210 10% 46%)',
  background: 'hsl(42 25% 97%)',
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
    savings: result.savings.median[index] ?? 0,
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

function downloadFile(content: string | Blob, filename: string, type?: string) {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
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
    canvas.width = Math.max(1200, svg.clientWidth * 2);
    canvas.height = Math.max(720, svg.clientHeight * 2);
    const context = canvas.getContext('2d');
    if (!context) return;
    context.fillStyle = COLORS.background;
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) downloadFile(blob, 'ai-water-break-even-chart.png');
    }, 'image/png');
    URL.revokeObjectURL(url);
  };
  image.src = url;
}

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function Header() {
  return (
    <header className="site-header">
      <div className="site-header-inner">
        <button data-testid="button-brand-home" onClick={() => scrollToSection('overview')} className="brand-lockup">
          <span className="brand-name">AI Water Break-Even</span>
          <span className="brand-subtitle">Monte Carlo demonstration</span>
        </button>
        <nav className="site-nav" aria-label="Page sections">
          <button onClick={() => scrollToSection('result')}>Simulation</button>
          <button onClick={() => scrollToSection('assumptions')}>Assumptions</button>
          <button onClick={() => scrollToSection('break-even')}>Break-even</button>
          <button onClick={() => scrollToSection('sensitivity')}>Sensitivity</button>
          <button onClick={() => scrollToSection('method')}>Method</button>
        </nav>
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
  hint?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  onChange: (value: number) => void;
  testId: string;
}) {
  return (
    <label className="slider-control">
      <div className="slider-heading">
        <span>
          <span className="slider-label">{label}</span>
          {hint && <span className="slider-hint">{hint}</span>}
        </span>
        <span className="slider-value">{display}</span>
      </div>
      <input data-testid={testId} aria-label={label} type="range" value={value} min={min} max={max} step={step} onChange={(event) => onChange(Number(event.target.value))} />
      <div className="slider-endpoints"><span>{min}</span><span>{max}</span></div>
    </label>
  );
}

function Assumptions({
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
  const [moreOpen, setMoreOpen] = useState(false);
  const update = <K extends keyof ScenarioConfig>(key: K, value: ScenarioConfig[K]) => setConfig({ ...config, [key]: value });

  return (
    <section id="assumptions" className="section-anchor section-block">
      <div className="section-heading">
        <div>
          <span className="section-number">03</span>
          <h2>Assumptions</h2>
        </div>
        <p>Change the variables that shape the cumulative balance.</p>
      </div>
      <div className="assumption-grid">
        <SliderControl label="AI growth" hint="Annual increase in simulated AI water demand" value={config.aiGrowthRate * 100} min={0} max={20} step={0.5} display={`${(config.aiGrowthRate * 100).toFixed(1)}% / year`} onChange={(value) => update('aiGrowthRate', value / 100)} testId="input-ai-growth" />
        <SliderControl label="Water-efficiency improvement" hint="Annual reduction in water intensity" value={config.efficiencyImprovement * 100} min={0} max={8} step={0.2} display={`${(config.efficiencyImprovement * 100).toFixed(1)}% / year`} onChange={(value) => update('efficiencyImprovement', value / 100)} testId="input-efficiency-improvement" />
        <SliderControl label="Savings potential" hint="Annual water that could be saved before realization" value={config.savingsPotential} min={0} max={2000} step={10} display={`${config.savingsPotential}M m³ / year`} onChange={(value) => update('savingsPotential', value)} testId="input-savings-potential" />
        <SliderControl label="Adoption" hint="Share of the potential intervention in use" value={config.adoptionRate * 100} min={0} max={100} step={1} display={`${Math.round(config.adoptionRate * 100)}%`} onChange={(value) => update('adoptionRate', value / 100)} testId="input-adoption" />
        <SliderControl label="Realization" hint="Share of theoretical savings that becomes realized" value={config.realizationFactor * 100} min={0} max={100} step={1} display={`${Math.round(config.realizationFactor * 100)}%`} onChange={(value) => update('realizationFactor', value / 100)} testId="input-realization" />
      </div>
      <div className="more-assumptions">
        <button data-testid="button-more-assumptions" onClick={() => setMoreOpen(!moreOpen)} className="more-assumptions-toggle">
          <span>More assumptions</span>
          {moreOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
        {moreOpen && (
          <div className="secondary-assumption-grid">
            <SliderControl label="Starting AI water use" hint="Annual operational water burden at year zero" value={config.startingWaterUse} min={CONFIG_LIMITS.startingWaterUse.min} max={CONFIG_LIMITS.startingWaterUse.max} step={CONFIG_LIMITS.startingWaterUse.step} display={`${config.startingWaterUse}M m³ / year`} onChange={(value) => update('startingWaterUse', value)} testId="input-starting-water-use" />
            <SliderControl label="AI attribution" hint="Share of realized savings credited to AI-enabled action" value={config.attributionFraction * 100} min={0} max={100} step={1} display={`${Math.round(config.attributionFraction * 100)}%`} onChange={(value) => update('attributionFraction', value / 100)} testId="input-attribution" />
            <SliderControl label="Time horizon" hint="Years included in each simulated path" value={config.horizon} min={10} max={80} step={1} display={`${config.horizon} years`} onChange={(value) => update('horizon', value)} testId="input-horizon" />
            <SliderControl label="Monte Carlo runs" hint="More runs make percentages more stable" value={config.simulations} min={250} max={20000} step={250} display={config.simulations.toLocaleString()} onChange={(value) => update('simulations', value)} testId="input-simulations" />
            <label className="seed-control">
              <span className="slider-label">Random seed</span>
              <span className="slider-hint">Same seed and assumptions reproduce the result</span>
              <input data-testid="input-seed" aria-label="Random seed" type="number" min={1} max={999999999} value={config.seed} onChange={(event) => update('seed', Number(event.target.value) || 1)} />
            </label>
          </div>
        )}
      </div>
      <div className="assumption-actions">
        <div className="run-status">
          {isRunning ? `Computing ${progress}% · ${config.simulations.toLocaleString()} simulations · seed ${config.seed}` : `${config.simulations.toLocaleString()} simulations · seed ${config.seed}`}
          {config.simulations < 1_000 && <span className="low-count-note">Low run count may be noisy.</span>}
        </div>
        <div className="action-group">
          <button data-testid="button-run-simulation" onClick={onRun} disabled={isRunning} className="recalculate-button">{isRunning ? 'Computing…' : 'Recalculate'}</button>
          <button onClick={onReset} className="text-action"><RotateCcw size={13} /> Reset</button>
          <button onClick={onRandomize} className="text-action">New seed</button>
        </div>
      </div>
    </section>
  );
}

function Legend({ color, children, dashed = false }: { color: string; children: string; dashed?: boolean }) {
  return <span className="legend-item"><i className={dashed ? 'legend-line legend-dashed' : 'legend-line'} style={{ backgroundColor: dashed ? 'transparent' : color, borderColor: color }} />{children}</span>;
}

function MainChart({ result }: { result: SimulationResult }) {
  const data = chartData(result);
  const crossing = medianCrossing(result);
  return (
    <div className="main-chart" data-testid="chart-cumulative-balance">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 10, left: -18, bottom: 8 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 11 }} tickFormatter={(year) => `Y${year}`} />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 11 }} tickFormatter={formatWater} width={50} />
          <Tooltip cursor={{ stroke: 'hsl(210 10% 46% / .3)' }} contentStyle={{ border: '1px solid hsl(40 11% 82%)', borderRadius: 0, background: COLORS.background, fontSize: 11 }} formatter={(value: number, name: string) => [`${formatWater(value)}M m³`, name === 'burden' ? 'Cumulative burden' : name === 'savings' ? 'Cumulative savings' : 'Net balance']} labelFormatter={(label) => `Year ${label}`} />
          <ReferenceLine y={0} stroke="hsl(210 10% 46% / .75)" strokeDasharray="4 4" label={{ value: 'Break-even', position: 'insideTopLeft', fill: COLORS.text, fontSize: 10 }} />
          <Area isAnimationActive={false} type="monotone" dataKey="netWideUpper" stroke="none" fill="hsl(210 10% 46% / .08)" />
          <Area isAnimationActive={false} type="monotone" dataKey="netWideLower" stroke="none" fill={COLORS.background} />
          <Area isAnimationActive={false} type="monotone" dataKey="netUpper" stroke="none" fill="hsl(210 10% 46% / .12)" />
          <Area isAnimationActive={false} type="monotone" dataKey="netLower" stroke="none" fill={COLORS.background} />
          <Line isAnimationActive={false} type="monotone" dataKey="burden" stroke={COLORS.burden} strokeWidth={2.5} dot={false} />
          <Line isAnimationActive={false} type="monotone" dataKey="savings" stroke={COLORS.savings} strokeWidth={2.5} dot={false} />
          <Line isAnimationActive={false} type="monotone" dataKey="net" stroke={COLORS.net} strokeWidth={1.7} strokeDasharray="5 4" dot={false} />
          {crossing !== null && <ReferenceLine x={crossing} stroke={COLORS.net} strokeDasharray="3 3" label={{ value: `Sustained break-even · Y${crossing}`, position: 'insideTopRight', fill: COLORS.net, fontSize: 10 }} />}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function ProbabilityPlot({ result }: { result: SimulationResult }) {
  const data = ([10, 20, 30, 50] as const).map((year) => ({ year, probability: result.probabilities[year] }));
  return (
    <div className="break-even-probability">
      <div className="subsection-heading">
        <div>
          <h3>Probability of sustained break-even</h3>
          <p>Share of simulated paths that reach zero and stay there.</p>
        </div>
        <p className="never-inline">Never reaches sustained break-even <strong>{formatPercent(result.neverProbability)}</strong></p>
      </div>
      <div className="probability-chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 8 }}>
            <CartesianGrid stroke={COLORS.grid} vertical={false} />
            <XAxis type="number" dataKey="year" domain={[10, 50]} ticks={[10, 20, 30, 50]} tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 11 }} tickFormatter={(year) => `${year} years`} />
            <YAxis domain={[0, 1]} tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 11 }} tickFormatter={formatPercent} width={42} />
            <Tooltip contentStyle={{ border: '1px solid hsl(40 11% 82%)', borderRadius: 0, background: COLORS.background, fontSize: 11 }} formatter={(value: number) => [formatPercent(value), 'Probability']} labelFormatter={(label) => `${label} years`} />
            <Line isAnimationActive={false} type="monotone" dataKey="probability" stroke={COLORS.savings} strokeWidth={2} dot={{ r: 4, fill: COLORS.savings, strokeWidth: 0 }} activeDot={{ r: 6 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function SimulationSection({ result }: { result: SimulationResult }) {
  const crossing = medianCrossing(result);
  return (
    <section id="result" className="section-anchor section-block simulation-section">
      <div className="simulation-heading">
        <div>
          <span className="section-number">01</span>
          <h2>Simulation</h2>
        </div>
      </div>
      <div className="chart-tools">
        <div className="chart-title">
          <h3>Cumulative water balance</h3>
          <p>AI water burden, AI-enabled savings, and their difference over time (million m³).</p>
        </div>
        <div className="export-actions">
          <button onClick={() => exportCSV(result)}>CSV</button>
          <button onClick={() => exportJSON(result)}>JSON</button>
          <button onClick={downloadChartPNG}>PNG</button>
        </div>
      </div>
      <MainChart result={result} />
      <div className="chart-caption">
        <div className="legend-row">
          <Legend color={COLORS.burden}>AI water burden</Legend>
          <Legend color={COLORS.savings}>AI-enabled savings</Legend>
          <Legend color={COLORS.net} dashed>Net balance</Legend>
          <span className="uncertainty-note">Shaded bands: middle 50% and middle 90% of paths</span>
        </div>
        <p data-testid="text-explanation" className="chart-annotation">{result.explanation}</p>
        {crossing === null && <p className="chart-annotation chart-annotation-warm">No sustained break-even within the selected horizon.</p>}
      </div>
      <ProbabilityPlot result={result} />
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
    <section className="section-block scenario-section" id="scenarios">
      <div className="section-heading">
        <div>
          <span className="section-number">05</span>
          <h2>Scenarios</h2>
        </div>
        <p>Same simulation structure, different assumptions.</p>
      </div>
      <div className="scenario-chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 14, right: 10, left: -18, bottom: 8 }}>
            <CartesianGrid stroke={COLORS.grid} vertical={false} />
            <XAxis dataKey="year" tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 11 }} tickFormatter={(year) => `Y${year}`} />
            <YAxis tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 11 }} tickFormatter={formatWater} width={50} />
            <Tooltip contentStyle={{ border: '1px solid hsl(40 11% 82%)', borderRadius: 0, background: COLORS.background, fontSize: 11 }} formatter={(value: number, name: string) => [`${formatWater(value)}M m³`, name]} labelFormatter={(label) => `Year ${label}`} />
            <ReferenceLine y={0} stroke="hsl(210 10% 46% / .75)" strokeDasharray="4 4" />
            {comparisons.map((scenario) => <Line isAnimationActive={false} key={scenario.name} type="monotone" dataKey={scenario.name} stroke={scenario.color} strokeWidth={2} dot={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="scenario-legend">
        {comparisons.map((scenario, index) => (
          <button key={scenario.name} onClick={() => onChooseScenario(index)} className="scenario-item">
            <span className="scenario-line" style={{ backgroundColor: scenario.color }} />
            <span>
              <strong>{scenario.name}</strong>
              <small>{index === 0 ? 'Current assumptions' : index === 1 ? 'Higher adoption, realization, and efficiency' : 'Higher growth, lower realized savings'}</small>
            </span>
            <em>{formatPercent(scenario.result.probabilities[30])} by Y30</em>
          </button>
        ))}
      </div>
    </section>
  );
}

function DistributionChart({ result }: { result: SimulationResult }) {
  return (
    <div className="distribution-chart" data-testid="chart-break-even-distribution">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={distributionData(result)} margin={{ top: 6, right: 4, left: -24, bottom: 2 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="range" tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 11 }} />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 11 }} />
          <Tooltip cursor={{ fill: 'hsl(190 45% 29% / .06)' }} contentStyle={{ border: '1px solid hsl(40 11% 82%)', borderRadius: 0, background: COLORS.background, fontSize: 11 }} formatter={(value: number) => [`${value.toLocaleString()} runs`, 'Simulations']} />
          <Bar isAnimationActive={false} dataKey="count" fill={COLORS.savings} barSize={42} radius={[1, 1, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function SensitivityChart({ sensitivity }: { sensitivity: ReturnType<typeof calculateSensitivity> }) {
  const max = Math.max(...sensitivity.map((item) => item.influence), 1);
  const data = sensitivity.map((item) => ({ ...item, influencePercent: (item.influence / max) * 100 }));
  return (
    <div className="sensitivity-chart" data-testid="chart-sensitivity">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart layout="vertical" data={data} margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={COLORS.grid} horizontal={false} />
          <XAxis type="number" domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fill: COLORS.text, fontSize: 10 }} unit="%" />
          <YAxis type="category" dataKey="label" width={145} tickLine={false} axisLine={false} tick={{ fill: 'hsl(210 17% 17%)', fontSize: 10 }} />
          <Tooltip cursor={{ fill: 'hsl(190 45% 29% / .05)' }} contentStyle={{ border: '1px solid hsl(40 11% 82%)', borderRadius: 0, background: COLORS.background, fontSize: 11 }} formatter={(value: number, name: string, item) => [name === 'influencePercent' ? `${value.toFixed(0)}% relative range` : value, item.payload.label]} />
          <Bar isAnimationActive={false} dataKey="influencePercent" fill={COLORS.burden} barSize={14} radius={[0, 1, 1, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DeeperAnalysis({ result, config }: { result: SimulationResult; config: ScenarioConfig }) {
  const [metric, setMetric] = useState<OutcomeMetric>('finalBalance');
  const sensitivity = useMemo(() => calculateSensitivity(config, metric), [config, metric]);
  return (
    <>
      <section id="break-even" className="section-anchor section-block deeper-section">
        <div className="section-heading">
          <div>
            <span className="section-number">04</span>
            <h2>Break-even</h2>
          </div>
          <p>When do simulated paths reach zero and stay there?</p>
        </div>
        <div className="distribution-chart-wrap">
          <DistributionChart result={result} />
          <p className="small-note">The final bar is the share of paths that never reach sustained break-even within the selected horizon.</p>
        </div>
      </section>
      <section id="sensitivity" className="section-anchor section-block sensitivity-section">
        <div className="section-heading">
          <div>
            <span className="section-number">06</span>
            <h2>Sensitivity</h2>
          </div>
          <div className="sensitivity-controls">
            <p>Sensitivity of the final balance</p>
            <select value={metric} onChange={(event) => setMetric(event.target.value as OutcomeMetric)} aria-label="Sensitivity outcome">
              <option value="finalBalance">Final net balance</option>
              <option value="probability30">Break-even by 30 years</option>
              <option value="probability50">Break-even by 50 years</option>
              <option value="breakEvenYear">Median break-even year</option>
            </select>
          </div>
        </div>
        <SensitivityChart sensitivity={sensitivity} />
        <p className="small-note">Relative change when each assumption is moved across its allowed range.</p>
      </section>
    </>
  );
}

function MethodSection({ result, config }: { result: SimulationResult; config: ScenarioConfig }) {
  const [open, setOpen] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  return (
    <section className="section-block method-section" id="method">
      <button data-testid="button-toggle-method" onClick={() => setOpen(!open)} className="method-toggle">
        <span><span className="section-number">07</span> Method</span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div className="method-content">
          <div className="method-grid">
            <div><strong>Monte Carlo simulation</strong><p>Each run samples uncertain assumptions and simulates cumulative burden and savings year by year.</p></div>
            <div><strong>Distributions</strong><p>Truncated normal and log-normal draws keep sampled values within their physical ranges.</p></div>
            <div><strong>Sustained break-even</strong><p>A path must reach zero or above and remain there through the end of the selected horizon.</p></div>
            <div><strong>Uncertainty</strong><p>Shaded bands show the middle 50% and middle 90% of simulated paths.</p></div>
          </div>
          <div className="method-note">
            <p><strong>Sign convention:</strong> cumulative AI-enabled water savings minus cumulative AI water burden. Positive values mean savings exceed burden.</p>
            <p><strong>Defaults:</strong> illustrative assumptions; not measured inputs or a forecast.</p>
          </div>
          <button onClick={() => setAdvanced(!advanced)} className="advanced-toggle">{advanced ? 'Hide details' : 'Show run details'}</button>
          {advanced && (
            <div className="run-details">
              <span>{config.simulations.toLocaleString()} simulations</span>
              <span>{config.horizon}-year horizon</span>
              <span>Seed {config.seed}</span>
              <span>Output from current ensemble</span>
              <span>Final median balance: {formatWater(result.finalMedianBalance)}M m³</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Home() {
  const [config, setConfig] = useState<ScenarioConfig>(DEFAULT_CONFIG);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [comparisons, setComparisons] = useState<ComparisonResult>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [lastRun, setLastRun] = useState('Reference case');
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
    const selected = comparisons[index]?.result.config;
    if (selected) {
      setConfig(selected);
      void runSimulation(selected, comparisons[index].name);
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
    void runSimulation(randomized, 'New seed');
  };

  return (
    <div className="research-page">
      <Header />
      <main className="research-shell">
        <section id="overview" className="section-anchor intro-section">
          <div className="intro-copy">
            <span className="section-number">AI Water Break-Even</span>
            <h1>AI water use and the savings it could enable</h1>
            <p>This simulation follows the cumulative balance between AI water demand and AI-enabled savings under uncertain assumptions. Change the assumptions to see how the distribution of break-even outcomes changes.</p>
            <small>Demonstration model. Default values are illustrative assumptions.</small>
          </div>
          {result && (
            <div className="intro-result">
              <span>30-year sustained break-even</span>
              <strong>{formatPercent(result.probabilities[30])}</strong>
              <span>of simulated paths</span>
              <small>{result.medianBreakEvenYear ? `Median sustained crossing: year ${result.medianBreakEvenYear}` : 'Median path does not reach sustained break-even'}</small>
            </div>
          )}
        </section>

        {runError && <p className="run-error">{runError}</p>}
        {result ? (
          <>
            <div className="run-line">{isRunning ? `Recalculating · ${progress}%` : `Current result · ${lastRun}`}</div>
            <SimulationSection result={result} />
            <Assumptions config={config} setConfig={setConfig} onRun={() => void runSimulation(config, 'Custom case')} onReset={() => { setConfig(DEFAULT_CONFIG); void runSimulation(DEFAULT_CONFIG, 'Reference case'); }} onRandomize={randomizeScenario} isRunning={isRunning} progress={progress} />
            <DeeperAnalysis result={result} config={config} />
            {comparisons.length > 0 && <ComparisonSection comparisons={comparisons} onChooseScenario={chooseScenario} />}
            <MethodSection result={result} config={config} />
          </>
        ) : (
          <div className="loading-state">Running the first simulation…</div>
        )}
        <footer className="site-footer">
          <span>Interactive Monte Carlo model. Default values are illustrative assumptions.</span>
          <br />
          <small>Made by Tazwar</small>
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