import { Tile } from '@/components/ui/Tile';
import { DistributionChart } from '@/components/visualization/DistributionChart';
import { formatPercent } from '@/lib/format';
import type { SimulationSummary } from '@/domain/model/types';

const LADDER: Array<{ year: 10 | 20 | 30 | 50; key: 'y10' | 'y20' | 'y30' | 'y50' }> = [
  { year: 10, key: 'y10' },
  { year: 20, key: 'y20' },
  { year: 30, key: 'y30' },
  { year: 50, key: 'y50' },
];

/**
 * Sustained break-even distribution: when paths cross (histogram) and the
 * cumulative probability ladder at the standard evaluation horizons.
 */
export function ProbabilityTile({ summary }: { summary: SimulationSummary | null }) {
  if (!summary) {
    return (
      <Tile
        index="02"
        title="Break-even distribution"
        note="First ensemble still computing."
        className="xl:col-span-4"
      >
        <div className="h-[190px] animate-pulse bg-ink/[0.05]" />
      </Tile>
    );
  }

  return (
    <Tile
      index="02"
      title="Break-even distribution"
      note="First sustained crossing year per path; the final bar never crosses."
      className="xl:col-span-4"
      footer={
        <span className="tabular-nums">
          Median crossing{' '}
          {summary.medianBreakEvenYear !== null
            ? `year ${summary.medianBreakEvenYear}`
            : 'not reached'}{' '}
          · {formatPercent(summary.neverProbability)} never cross
        </span>
      }
    >
      <DistributionChart summary={summary} />
      <div className="mt-4 space-y-2.5">
        {LADDER.map(({ year, key }) => {
          const probability = summary.probabilities[key];
          return (
            <div key={year} className="flex items-center gap-3">
              <span className="w-10 text-[10px] font-semibold uppercase tracking-[0.1em] text-muted">
                Y{year}
              </span>
              <div className="h-[6px] flex-1 bg-ink/[0.07]">
                <div
                  className="h-full bg-teal transition-[width] duration-300 ease-out"
                  style={{ width: `${Math.round(probability * 100)}%` }}
                />
              </div>
              <span className="w-11 text-right text-[11px] font-medium text-ink tabular-nums">
                {formatPercent(probability)}
              </span>
            </div>
          );
        })}
      </div>
    </Tile>
  );
}
