import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Tile } from '@/components/ui/Tile';
import { formatPercent, formatWater } from '@/lib/format';
import {
  SENSITIVITY_METRIC_LABELS,
  type SensitivityMetric,
  type SensitivityResult,
} from '@/domain/model/types';

const RUST = '#b3542e';
const GRID = 'rgba(63,56,44,0.10)';
const TEXT = '#6f675c';

function formatMetricValue(metric: SensitivityMetric, value: number): string {
  switch (metric) {
    case 'finalBalance':
      return `${formatWater(value)} M m³`;
    case 'breakEvenYear':
      return `Y${Math.round(value)}`;
    default:
      return formatPercent(value, 1);
  }
}

interface TornadoRow {
  label: string;
  offset: number;
  span: number;
  low: number;
  high: number;
}

function buildRows(results: SensitivityResult[]): { rows: TornadoRow[]; axisMin: number; axisMax: number } {
  const values = results.flatMap((result) => [result.low, result.high, result.baseline]);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const pad = (rawMax - rawMin) * 0.06 || Math.abs(rawMax) * 0.06 || 1;
  const axisMin = rawMin - pad;
  const axisMax = rawMax + pad;
  const rows = results.map((result) => {
    const from = Math.min(result.low, result.high);
    const to = Math.max(result.low, result.high);
    return {
      label: result.label,
      offset: from - axisMin,
      span: to - from,
      low: result.low,
      high: result.high,
    };
  });
  return { rows, axisMin, axisMax };
}

function TornadoTooltip({
  active,
  payload,
  baseline,
  metric,
}: {
  active?: boolean;
  payload?: Array<{ dataKey?: string | number; payload?: TornadoRow & { baseline: number } }>;
  baseline: number;
  metric: SensitivityMetric;
}) {
  const row = payload?.find((entry) => entry.dataKey === 'span')?.payload;
  if (!active || !row) return null;
  return (
    <div className="min-w-[210px] border border-line bg-surface px-3 py-2.5 text-[11px] shadow-sm">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
        {row.label}
      </div>
      <div className="flex justify-between gap-6 tabular-nums">
        <span className="text-ink-soft">Parameter at low</span>
        <span className="font-medium text-ink">{formatMetricValue(metric, row.low)}</span>
      </div>
      <div className="flex justify-between gap-6 tabular-nums">
        <span className="text-ink-soft">Parameter at high</span>
        <span className="font-medium text-ink">{formatMetricValue(metric, row.high)}</span>
      </div>
      <div className="mt-1.5 flex justify-between gap-6 border-t border-dashed border-line pt-1.5 tabular-nums">
        <span className="text-muted">Baseline (untouched)</span>
        <span className="text-ink-soft">{formatMetricValue(metric, baseline)}</span>
      </div>
    </div>
  );
}

interface SensitivityTornadoProps {
  results: SensitivityResult[];
  metric: SensitivityMetric;
  onMetricChange: (metric: SensitivityMetric) => void;
}

/**
 * One-low / one-high tornado ranking all eight parameters by their pull on
 * the selected outcome. Bars span the low↔high outcome range on a shared
 * axis centered by the untouched baseline.
 */
export function SensitivityTornado({ results, metric, onMetricChange }: SensitivityTornadoProps) {
  const { rows, axisMin, axisMax } = useMemo(() => buildRows(results), [results]);
  const baseline = results[0]?.baseline ?? 0;

  return (
    <Tile
      index="05"
      title="Parameter sensitivity"
      note="Outcome range when each assumption moves low ↔ high with the rest held fixed."
      className="xl:col-span-7"
      data-testid="chart-sensitivity"
      actions={
        <label className="flex items-center gap-2 text-[10px] uppercase tracking-[0.1em] text-muted">
          Outcome
          <select
            aria-label="Sensitivity outcome"
            value={metric}
            onChange={(event) => onMetricChange(event.target.value as SensitivityMetric)}
            className="cursor-pointer border border-line bg-surface px-2 py-1 text-[11px] normal-case tracking-normal text-ink focus-visible:outline-2 focus-visible:outline-teal"
          >
            {(Object.keys(SENSITIVITY_METRIC_LABELS) as SensitivityMetric[]).map((key) => (
              <option key={key} value={key}>
                {SENSITIVITY_METRIC_LABELS[key]}
              </option>
            ))}
          </select>
        </label>
      }
      footer="Probes run at a capped path count with deterministic per-parameter seed offsets; ranked by absolute influence."
    >
      <div className="h-[330px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 4, right: 16, left: 8, bottom: 0 }}
            barCategoryGap="28%"
          >
            <CartesianGrid stroke={GRID} horizontal={false} />
            <XAxis
              type="number"
              domain={[axisMin, axisMax]}
              tickLine={false}
              axisLine={{ stroke: GRID }}
              tick={{ fill: TEXT, fontSize: 9 }}
              tickFormatter={(value: number) => formatMetricValue(metric, value)}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={150}
              tickLine={false}
              axisLine={false}
              tick={{ fill: '#3f382c', fontSize: 10 }}
            />
            <Tooltip
              cursor={{ fill: 'rgba(63,56,44,0.04)' }}
              content={
                <TornadoTooltip baseline={baseline} metric={metric} />
              }
            />
            <Bar dataKey="offset" stackId="tornado" fill="transparent" isAnimationActive={false} />
            <Bar
              dataKey="span"
              stackId="tornado"
              fill={RUST}
              radius={[1, 1, 1, 1]}
              barSize={13}
              isAnimationActive={false}
            />
            <ReferenceLine
              x={baseline}
              stroke="rgba(63,56,44,0.6)"
              strokeDasharray="3 3"
              label={{ value: 'Baseline', position: 'insideBottomRight', fill: TEXT, fontSize: 9 }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Tile>
  );
}
