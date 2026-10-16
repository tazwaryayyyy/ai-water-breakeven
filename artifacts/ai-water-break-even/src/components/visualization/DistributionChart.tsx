import { useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { formatInt } from '@/lib/format';
import type { SimulationSummary } from '@/domain/model/types';

const TEAL = '#12766b';
const RUST = '#b3542e';
const GRID = 'rgba(63,56,44,0.10)';
const TEXT = '#6f675c';

interface Bin {
  label: string;
  count: number;
  share: number;
  never: boolean;
}

function binBreakEvenYears(summary: SimulationSummary): Bin[] {
  const horizon = summary.config.horizon;
  const width = horizon > 45 ? 10 : 5;
  const bins: Bin[] = [];
  for (let from = 1; from <= horizon; from += width) {
    const to = Math.min(from + width - 1, horizon);
    let count = 0;
    for (let year = from; year <= to; year++) count += summary.breakEvenCounts[year - 1] ?? 0;
    bins.push({
      label: from === to ? `${from}` : `${from}–${to}`,
      count,
      share: count / summary.config.simulations,
      never: false,
    });
  }
  bins.push({
    label: 'Never',
    count: summary.neverCount,
    share: summary.neverProbability,
    never: true,
  });
  return bins;
}

function HistogramTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload?: Bin }>;
}) {
  if (!active || !payload?.[0]?.payload) return null;
  const bin = payload[0].payload;
  return (
    <div className="border border-line bg-surface px-3 py-2 text-[11px] shadow-sm">
      <div className="font-semibold text-ink">
        {bin.never ? 'Never breaks even' : `Years ${bin.label}`}
      </div>
      <div className="mt-1 text-ink-soft tabular-nums">
        {formatInt(bin.count)} paths · {(bin.share * 100).toFixed(1)}%
      </div>
    </div>
  );
}

/** Binned histogram of sustained break-even years across the ensemble. */
export function DistributionChart({ summary }: { summary: SimulationSummary }) {
  const bins = useMemo(() => binBreakEvenYears(summary), [summary]);
  return (
    <div data-testid="chart-break-even-distribution" className="h-[190px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={bins} margin={{ top: 4, right: 4, left: 0, bottom: 0 }} barCategoryGap="18%">
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={{ stroke: GRID }}
            tick={{ fill: TEXT, fontSize: 9 }}
            interval={0}
          />
          <YAxis
            tickLine={false}
            axisLine={false}
            tick={{ fill: TEXT, fontSize: 9 }}
            width={30}
            tickFormatter={(value: number) => formatInt(value)}
          />
          <Tooltip cursor={{ fill: 'rgba(63,56,44,0.05)' }} content={<HistogramTooltip />} />
          <Bar isAnimationActive={false} dataKey="count" radius={[1, 1, 0, 0]}>
            {bins.map((bin) => (
              <Cell key={bin.label} fill={bin.never ? RUST : TEAL} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
