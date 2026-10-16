import { useMemo } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Button } from '@/components/ui/Button';
import { Tile } from '@/components/ui/Tile';
import { formatPercent, formatWater } from '@/lib/format';
import type { ScenarioOutcome } from '@/domain/model/types';

const GRID = 'rgba(63,56,44,0.10)';
const TEXT = '#6f675c';

interface ScenarioComparisonProps {
  outcomes: ScenarioOutcome[];
  horizon: number;
  onApply: (scenarioName: string) => void;
}

function ScenarioTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ dataKey?: string | number; value?: number; color?: string; payload?: Record<string, number> }>;
  label?: number | string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="min-w-[190px] border border-line bg-surface px-3 py-2.5 text-[11px] shadow-sm">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
        Year {label}
      </div>
      {payload.map((entry) => (
        <div key={String(entry.dataKey)} className="flex items-center justify-between gap-5">
          <span className="flex items-center gap-2 text-ink-soft">
            <i className="inline-block h-[2px] w-4" style={{ backgroundColor: entry.color }} />
            {String(entry.dataKey)}
          </span>
          <span className="font-medium text-ink tabular-nums">
            {formatWater(entry.value ?? 0)} M m³
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Baseline vs Accelerated Savings vs High Growth: median net-balance
 * trajectories with per-scenario break-even stats. Rows double as buttons
 * that load the scenario's assumptions into the controls.
 */
export function ScenarioComparison({ outcomes, horizon, onApply }: ScenarioComparisonProps) {
  const data = useMemo(() => {
    if (!outcomes.length) return [];
    return Array.from({ length: horizon }, (_, index) => {
      const point: Record<string, number> = { year: index + 1 };
      for (const outcome of outcomes) {
        point[outcome.name] = outcome.medianBalance[index] ?? 0;
      }
      return point;
    });
  }, [outcomes, horizon]);

  return (
    <Tile
      index="06"
      title="Scenario comparison"
      note="Same engine, three futures. Click a row to load its assumptions."
      className="xl:col-span-5"
      footer="Scenario passes run at a capped path count for responsiveness; the main ensemble stays at full size."
    >
      <div className="h-[210px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey="year"
              tickLine={false}
              axisLine={false}
              tick={{ fill: TEXT, fontSize: 10 }}
              tickFormatter={(year: number) => `Y${year}`}
              minTickGap={18}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              tick={{ fill: TEXT, fontSize: 10 }}
              width={52}
              tickFormatter={(value: number) => formatWater(value)}
            />
            <Tooltip content={<ScenarioTooltip />} cursor={{ stroke: 'rgba(63,56,44,0.25)' }} />
            <ReferenceLine y={0} stroke="rgba(63,56,44,0.65)" strokeDasharray="4 4" />
            {outcomes.map((outcome) => (
              <Line
                key={outcome.name}
                isAnimationActive={false}
                type="monotone"
                dataKey={outcome.name}
                stroke={outcome.color}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 divide-y divide-line border-t border-line">
        {outcomes.map((outcome) => (
          <div key={outcome.name} className="flex items-center gap-3 py-2.5">
            <i className="h-[3px] w-6 shrink-0" style={{ backgroundColor: outcome.color }} />
            <div className="min-w-0 flex-1">
              <div className="text-[12px] font-semibold text-ink">{outcome.name}</div>
              <div className="truncate text-[11px] text-muted">{outcome.description}</div>
            </div>
            <div className="text-right text-[11px] leading-tight text-ink-soft tabular-nums">
              <div>
                {formatPercent(outcome.probability30)} <span className="text-muted">by Y30</span>
              </div>
              <div>
                {outcome.medianBreakEvenYear !== null
                  ? `median cross Y${outcome.medianBreakEvenYear}`
                  : `final ${formatWater(outcome.finalMedianBalance)}`}
              </div>
            </div>
            <Button
              size="sm"
              variant="ghost"
              aria-label={`Load ${outcome.name} assumptions`}
              onClick={() => onApply(outcome.name)}
            >
              Load
            </Button>
          </div>
        ))}
      </div>
    </Tile>
  );
}
