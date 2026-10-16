import { useMemo, type ReactElement } from 'react';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Button } from '@/components/ui/Button';
import { Tile } from '@/components/ui/Tile';
import { formatWater } from '@/lib/format';
import type { SimulationSummary } from '@/domain/model/types';

const TEAL = '#12766b';
const RUST = '#b3542e';
const INK = '#3f382c';
const GRID = 'rgba(63,56,44,0.10)';
const TEXT = '#6f675c';
/** Neutral uncertainty ink for the net-balance bands. */
const BAND_WIDE = 'rgba(63,56,44,0.08)';
const BAND_MID = 'rgba(63,56,44,0.15)';

interface BalancePoint {
  year: number;
  burden: number;
  savings: number;
  net: number;
  band90Base: number;
  band90Span: number;
  band50Base: number;
  band50Span: number;
  netP5: number;
  netP95: number;
}

function buildData(summary: SimulationSummary): BalancePoint[] {
  const { years, burden, savings, balance } = summary;
  return years.map((year, i) => {
    const p5 = balance.p5[i];
    const p25 = balance.p25[i];
    const p75 = balance.p75[i];
    const p95 = balance.p95[i];
    return {
      year,
      burden: burden.median[i],
      savings: savings.median[i],
      net: balance.median[i],
      band90Base: p5,
      band90Span: p25 - p5,
      band50Base: p25,
      band50Span: p75 - p25,
      netP5: p5,
      netP95: p95,
    };
  });
}

/** First year the median curve is ≥ 0 and stays ≥ 0 to the horizon. */
function medianCrossing(data: BalancePoint[]): number | null {
  for (let i = 0; i < data.length; i++) {
    if (data[i].net >= 0 && data.slice(i).every((point) => point.net >= 0)) {
      return data[i].year;
    }
  }
  return null;
}

interface TooltipEntry {
  dataKey?: string | number;
  payload?: BalancePoint;
}

function BalanceTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: number | string;
}) {
  const point = payload?.find((entry) => entry.dataKey === 'net')?.payload;
  if (!active || !point) return null;
  const row = (color: string, name: string, value: number): ReactElement => (
    <div key={name} className="flex items-center justify-between gap-6">
      <span className="flex items-center gap-2 text-ink-soft">
        <i className="inline-block h-[2px] w-4" style={{ backgroundColor: color }} />
        {name}
      </span>
      <span className="font-medium text-ink tabular-nums">{formatWater(value)} M m³</span>
    </div>
  );
  return (
    <div className="min-w-[220px] border border-line bg-surface px-3 py-2.5 text-[11px] shadow-sm">
      <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted">
        Year {label}
      </div>
      {row(RUST, 'Cumulative burden', point.burden)}
      {row(TEAL, 'Cumulative savings', point.savings)}
      {row(INK, 'Net balance · median', point.net)}
      <div className="mt-1.5 border-t border-dashed border-line pt-1.5 text-muted tabular-nums">
        Net 90% band {formatWater(point.netP5)} … {formatWater(point.netP95)}
      </div>
    </div>
  );
}

interface MainBalanceChartProps {
  summary: SimulationSummary | null;
  onExportPNG: (selector: string) => void;
}

/**
 * The anchor visual: median burden, savings, and net trajectories with
 * stacked-area 50%/90% uncertainty bands around the net position, plus the
 * sustained crossing marker. All animations off for 60 FPS scrubbing.
 */
export function MainBalanceChart({ summary, onExportPNG }: MainBalanceChartProps) {
  const data = useMemo(() => (summary ? buildData(summary) : []), [summary]);
  const crossing = useMemo(() => (data.length ? medianCrossing(data) : null), [data]);
  const domain = useMemo<['dataMin' | number, 'dataMax' | number]>(() => {
    if (!data.length) return ['dataMin', 'dataMax'];
    let min = 0;
    let max = 0;
    for (const point of data) {
      min = Math.min(min, point.netP5, point.burden, point.savings);
      max = Math.max(max, point.netP95, point.burden, point.savings);
    }
    const pad = (max - min) * 0.05;
    return [min - pad, max + pad];
  }, [data]);

  return (
    <Tile
      index="03"
      title="Cumulative water balance"
      note="Medians with the middle 50% and 90% of paths shaded around the net position (M m³)."
      className="xl:col-span-12"
      data-testid="chart-cumulative-balance"
      actions={
        <Button size="sm" variant="ghost" onClick={() => onExportPNG('[data-testid="chart-cumulative-balance"]')}>
          PNG
        </Button>
      }
      footer={
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
          <span className="flex items-center gap-2">
            <i className="inline-block h-[2.5px] w-5" style={{ backgroundColor: RUST }} /> Burden
          </span>
          <span className="flex items-center gap-2">
            <i className="inline-block h-[2.5px] w-5" style={{ backgroundColor: TEAL }} /> Savings
          </span>
          <span className="flex items-center gap-2">
            <i
              className="inline-block h-0 w-5 border-t-2 border-dashed"
              style={{ borderColor: INK }}
            />
            Net (dashed)
          </span>
          {crossing !== null ? (
            <span className="text-ink-soft">Median sustained crossing: year {crossing}</span>
          ) : (
            <span className="text-rust">Median path never reaches sustained break-even</span>
          )}
        </div>
      }
    >
      <div className="h-[400px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 12, right: 8, left: 0, bottom: 4 }}>
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
              domain={domain}
              tickFormatter={(value: number) => formatWater(value)}
            />
            <Tooltip content={<BalanceTooltip />} cursor={{ stroke: 'rgba(63,56,44,0.25)' }} />
            <ReferenceLine
              y={0}
              stroke="rgba(63,56,44,0.65)"
              strokeDasharray="4 4"
              label={{ value: 'Break-even', position: 'insideTopLeft', fill: TEXT, fontSize: 9 }}
            />
            {/* 90% band: transparent base + shaded span, stacked. */}
            <Area
              isAnimationActive={false}
              dataKey="band90Base"
              stackId="b90"
              stroke="none"
              fill="transparent"
              legendType="none"
            />
            <Area
              isAnimationActive={false}
              dataKey="band90Span"
              stackId="b90"
              stroke="none"
              fill={BAND_WIDE}
              legendType="none"
            />
            {/* 50% band on its own stack. */}
            <Area
              isAnimationActive={false}
              dataKey="band50Base"
              stackId="b50"
              stroke="none"
              fill="transparent"
              legendType="none"
            />
            <Area
              isAnimationActive={false}
              dataKey="band50Span"
              stackId="b50"
              stroke="none"
              fill={BAND_MID}
              legendType="none"
            />
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey="burden"
              stroke={RUST}
              strokeWidth={2.5}
              dot={false}
            />
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey="savings"
              stroke={TEAL}
              strokeWidth={2.5}
              dot={false}
            />
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey="net"
              stroke={INK}
              strokeWidth={1.6}
              strokeDasharray="5 4"
              dot={false}
            />
            {crossing !== null && (
              <ReferenceLine
                x={crossing}
                stroke={TEAL}
                strokeDasharray="3 3"
                label={{
                  value: `Sustained · Y${crossing}`,
                  position: 'insideTopRight',
                  fill: TEAL,
                  fontSize: 9,
                }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </Tile>
  );
}
