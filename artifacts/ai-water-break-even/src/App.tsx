import { Activity, FileJson, FileSpreadsheet } from 'lucide-react';
import { BentoGrid } from '@/components/bento/BentoGrid';
import { MetricTile } from '@/components/bento/MetricTile';
import { ProbabilityTile } from '@/components/bento/ProbabilityTile';
import { ParameterScrubber, PARAMETER_SPECS } from '@/components/controls/ParameterScrubber';
import { ScenarioSelector } from '@/components/controls/ScenarioSelector';
import { MainBalanceChart } from '@/components/visualization/MainBalanceChart';
import { SensitivityTornado } from '@/components/visualization/SensitivityTornado';
import { ScenarioComparison } from '@/components/visualization/ScenarioComparison';
import { Button } from '@/components/ui/Button';
import { Tile } from '@/components/ui/Tile';
import { useSimulation } from '@/hooks/useSimulation';
import { useExport } from '@/hooks/useExport';
import { formatInt } from '@/lib/format';
import {
  SCENARIO_DEFINITIONS,
  SCENARIO_PRESETS,
} from '@/domain/model/simulation-engine';
import { PARAMETER_LIMITS } from '@/domain/model/types';

const STAGE_LABELS: Record<'baseline' | 'sensitivity' | 'scenarios', string> = {
  baseline: 'Ensemble',
  sensitivity: 'Sensitivity probes',
  scenarios: 'Scenario comparison',
};

function Masthead({
  isComputing,
  stage,
  fraction,
  onExportCSV,
  onExportJSON,
}: {
  isComputing: boolean;
  stage: 'baseline' | 'sensitivity' | 'scenarios' | null;
  fraction: number | null;
  onExportCSV: () => void;
  onExportJSON: () => void;
}) {
  const percent = fraction !== null ? Math.round(fraction * 100) : null;
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto flex w-full max-w-[1440px] items-center justify-between gap-4 px-4 py-3 md:px-8">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-lg leading-none tracking-tight text-ink">
            AI Water Break-Even
          </span>
          <span className="hidden text-[9.5px] font-semibold uppercase tracking-[0.16em] text-muted sm:inline">
            Monte Carlo research simulator
          </span>
        </div>
        <div className="flex items-center gap-2.5">
          <span
            className={
              'flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.1em] tabular-nums ' +
              (isComputing ? 'text-teal' : 'text-muted')
            }
            aria-live="polite"
            data-testid="computing-indicator"
          >
            {isComputing ? (
              <>
                <Activity size={12} className="animate-pulse" />
                {stage ? STAGE_LABELS[stage] : 'Computing'}
                {percent !== null ? ` · ${percent}%` : ''}
              </>
            ) : (
              'Worker idle'
            )}
          </span>
          <Button size="sm" variant="outline" onClick={onExportCSV} aria-label="Export ensemble as CSV">
            <FileSpreadsheet size={12} /> CSV
          </Button>
          <Button size="sm" variant="outline" onClick={onExportJSON} aria-label="Export simulation as JSON">
            <FileJson size={12} /> JSON
          </Button>
        </div>
      </div>
      <div className="h-[2px] w-full bg-transparent">
        {isComputing && (
          <div
            className="h-full bg-teal transition-[width] duration-200 ease-out"
            style={{ width: `${percent ?? 0}%` }}
          />
        )}
      </div>
    </header>
  );
}

export default function App() {
  const simulation = useSimulation();
  const {
    config,
    setConfig,
    result,
    error,
    computing,
    sensitivityMetric,
    activePreset,
    updateParameter,
    applyPreset,
    reset,
    newSeed,
  } = simulation;
  const { exportCSV, exportJSON, exportPNG } = useExport(result);

  const applyScenarioByName = (name: string) => {
    const definition = SCENARIO_DEFINITIONS.find((entry) => entry.name === name);
    if (!definition) return;
    setConfig(definition.derive(config));
  };

  return (
    <div className="min-h-screen bg-paper font-sans text-ink antialiased">
      <Masthead
        isComputing={computing.isComputing}
        stage={computing.stage}
        fraction={computing.fraction}
        onExportCSV={exportCSV}
        onExportJSON={exportJSON}
      />

      <main className="mx-auto w-full max-w-[1440px] px-4 pb-6 md:px-8">
        <section className="border-b border-line py-8 md:py-10">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-teal">
            Monte Carlo ensemble · sustained break-even analysis
          </p>
          <h1 className="mt-3 max-w-3xl font-display text-[34px] leading-[1.08] tracking-tight text-ink md:text-[44px]">
            AI water use and the savings it could enable
          </h1>
          <p className="mt-4 max-w-2xl text-[13.5px] leading-relaxed text-ink-soft">
            Every path pairs a compounding AI water burden with AI-enabled savings that ramp in as
            adoption grows. The question is not whether savings cross burden — it is whether they
            cross and <em className="font-display">stay</em> crossed. All {formatInt(config.simulations)}{' '}
            paths run off the main thread in a dedicated Web Worker; sliders re-dispatch a fresh
            ensemble in about a tenth of a second.
          </p>
        </section>

        {error && (
          <div role="alert" className="mt-4 border border-rust/40 bg-rust/[0.06] px-4 py-3 text-[12px] text-rust">
            {error}
          </div>
        )}

        <div className="mt-4 md:mt-6">
          <BentoGrid>
            <MetricTile result={result} sensitivity={result?.sensitivity ?? []} />
            <ProbabilityTile summary={result?.summary ?? null} />
            <MainBalanceChart summary={result?.summary ?? null} onExportPNG={exportPNG} />

            <Tile
              index="04"
              title="Assumptions"
              note="Scrub any value — the ensemble recomputes when you pause."
              className="xl:col-span-12"
              footer={
                <span className="tabular-nums">
                  {formatInt(config.simulations)} paths · {config.horizon}-year horizon · seed{' '}
                  {formatInt(config.seed)}
                  {config.simulations < 1000 ? ' · low path count may look noisy' : ''}
                </span>
              }
            >
              <ScenarioSelector
                presets={SCENARIO_PRESETS}
                activePreset={activePreset}
                onSelect={applyPreset}
                onReset={reset}
                onNewSeed={newSeed}
              />
              <div className="my-6 border-t border-dashed border-line" />
              <div className="grid gap-x-8 gap-y-6 md:grid-cols-2 xl:grid-cols-4">
                {PARAMETER_SPECS.map((spec) => (
                  <ParameterScrubber
                    key={spec.key}
                    label={spec.label}
                    hint={spec.hint}
                    unit={spec.unit}
                    display={spec.display}
                    value={config[spec.key]}
                    min={PARAMETER_LIMITS[spec.key].min}
                    max={PARAMETER_LIMITS[spec.key].max}
                    step={PARAMETER_LIMITS[spec.key].step}
                    onChange={(value) => updateParameter(spec.key, value)}
                    testId={`input-${spec.key}`}
                  />
                ))}
                <ParameterScrubber
                  label="Time horizon"
                  hint="Years simulated per path"
                  unit="yr"
                  value={config.horizon}
                  min={PARAMETER_LIMITS.horizon.min}
                  max={PARAMETER_LIMITS.horizon.max}
                  step={PARAMETER_LIMITS.horizon.step}
                  display={(v) => `${v} yr`}
                  onChange={(value) => updateParameter('horizon', value)}
                  testId="input-horizon"
                />
                <ParameterScrubber
                  label="Monte Carlo paths"
                  hint="More paths steady the percentiles"
                  unit="paths"
                  value={config.simulations}
                  min={PARAMETER_LIMITS.simulations.min}
                  max={PARAMETER_LIMITS.simulations.max}
                  step={PARAMETER_LIMITS.simulations.step}
                  display={(v) => formatInt(v)}
                  onChange={(value) => updateParameter('simulations', value)}
                  testId="input-simulations"
                />
                <div>
                  <label
                    htmlFor="input-seed"
                    className="text-[11px] font-semibold text-ink"
                  >
                    Random seed
                  </label>
                  <p className="mt-0.5 text-[10.5px] text-muted">
                    Same seed and assumptions reproduce the ensemble exactly.
                  </p>
                  <input
                    id="input-seed"
                    data-testid="input-seed"
                    type="number"
                    min={PARAMETER_LIMITS.seed.min}
                    max={PARAMETER_LIMITS.seed.max}
                    step={1}
                    value={config.seed}
                    onChange={(event) =>
                      updateParameter('seed', Math.round(Number(event.target.value)) || 1)
                    }
                    className="mt-2 w-full border border-line bg-surface px-2.5 py-1.5 font-display text-[14px] text-ink tabular-nums focus-visible:border-teal focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal"
                  />
                </div>
              </div>
            </Tile>

            <SensitivityTornado
              results={result?.sensitivity ?? []}
              metric={sensitivityMetric}
              onMetricChange={simulation.setSensitivityMetric}
            />
            {result && (
              <ScenarioComparison
                outcomes={result.scenarios}
                horizon={config.horizon}
                onApply={applyScenarioByName}
              />
            )}
          </BentoGrid>
        </div>

        <footer className="mt-8 border-t border-line pt-6">
          <div className="grid gap-8 text-[11px] leading-relaxed text-ink-soft md:grid-cols-3">
            <div>
              <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink">
                Method
              </h3>
              <p>
                Ensembles run in a dedicated Web Worker over flat Float64Arrays. Draws come from a
                xoshiro128** generator (SplitMix32-seeded, 32-bit Math.imul arithmetic — no BigInt)
                with Box–Muller normals, truncated-normal and log-normal parameter sampling.
                Quantiles are read from in-place sorted year slices.
              </p>
            </div>
            <div>
              <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink">
                Path equations
              </h3>
              <p className="font-display italic">
                W<sub>b</sub>(t) = W₀ · (1 + g<sub>ai</sub>)<sup>t</sup> · (1 − e<sub>w</sub>)
                <sup>t</sup>
                <br />
                W<sub>s</sub>(t) = S₀ · 1.022<sup>t</sup> · a(1 − e<sup>−0.105t</sup>) · E · R · F
              </p>
              <p className="mt-2">
                A path breaks even at year T only if its net balance stays ≥ 0 from T through the
                horizon, found by scanning backwards for the last negative year.
              </p>
            </div>
            <div>
              <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-ink">
                Reading the model
              </h3>
              <p>
                Net balance = cumulative AI-enabled savings − cumulative AI water burden; positive
                means savings lead. Volumes are millions of m³. Defaults are illustrative
                assumptions, not measured inputs or a forecast.
              </p>
            </div>
          </div>
          <div className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4 text-[9.5px] uppercase tracking-[0.16em] text-muted">
            <span>Interactive Monte Carlo model · illustrative assumptions</span>
            <span>Made by Tazwar</span>
          </div>
        </footer>
      </main>
    </div>
  );
}
