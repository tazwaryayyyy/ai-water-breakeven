/**
 * Editorial formatting helpers and physical water equivalents.
 *
 * Volumes are millions of cubic meters (M m³). Reference quantities:
 *   Olympic swimming pool  = 2,500 m³
 *   Lake Mead capacity     = 32,200 M m³
 *   City of 500k residents = 50 M m³ per year
 */

const OLYMPIC_POOL_M3 = 2500;
const LAKE_MEAD_MILLION_M3 = 32200;
const CITY_500K_ANNUAL_MILLION_M3 = 50;

const intFormatter = new Intl.NumberFormat('en-US');
const oneDecimal = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const twoDecimals = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/** Compact volume label in M m³ (e.g. 1,250 or 12.5k). */
export function formatWater(value: number): string {
  const absolute = Math.abs(value);
  if (absolute >= 10_000) return `${oneDecimal.format(value / 1000)}k`;
  if (absolute >= 100) return intFormatter.format(Math.round(value));
  return twoDecimals.format(value);
}

export function formatInt(value: number): string {
  return intFormatter.format(value);
}

export function formatPercent(fraction: number, digits = 0): string {
  const percent = fraction * 100;
  if (Number.isInteger(percent) || digits === 0) {
    return `${Math.round(percent)}%`;
  }
  return `${new Intl.NumberFormat('en-US', { maximumFractionDigits: digits }).format(percent)}%`;
}

export interface PhysicalEquivalents {
  /** Signed volume expressed in Olympic swimming pools (2,500 m³). */
  pools: number;
  /** Share of Lake Mead's full capacity (32,200 M m³), as a fraction. */
  lakeMeadShare: number;
  /** Years of annual water demand for a city of 500,000 residents. */
  cityYears: number;
  negative: boolean;
}

export function physicalEquivalents(millionM3: number): PhysicalEquivalents {
  const pools = (millionM3 * 1_000_000) / OLYMPIC_POOL_M3;
  return {
    pools,
    lakeMeadShare: Math.abs(millionM3) / LAKE_MEAD_MILLION_M3,
    cityYears: millionM3 / CITY_500K_ANNUAL_MILLION_M3,
    negative: millionM3 < 0,
  };
}

/** "≈ 18,400 pools" style short label for inline callouts. */
export function formatPools(pools: number): string {
  if (Math.abs(pools) >= 1000) return `${formatInt(Math.round(pools))} pools`;
  if (Math.abs(pools) >= 10) return `${Math.round(pools)} pools`;
  return `${oneDecimal.format(pools)} pools`;
}

/** Human-share label such as "0.4% of Lake Mead". */
export function formatLakeShare(share: number): string {
  const percent = share * 100;
  if (percent < 0.1) return '<0.1% of Lake Mead';
  if (percent >= 100) return `${Math.round(percent)}% of Lake Mead`;
  return `${oneDecimal.format(percent)}% of Lake Mead`;
}

/** "2.6 years of city demand (500k residents)". */
export function formatCityYears(cityYears: number): string {
  const absolute = Math.abs(cityYears);
  const magnitude =
    absolute >= 100 ? formatInt(Math.round(absolute)) : oneDecimal.format(absolute);
  return `${magnitude} yr of city demand (500k)`;
}

/**
 * One-sentence editorial reading of the ensemble, in the spirit of a
 * research abstract rather than a dashboard tooltip.
 */
export function buildNarrative(
  probabilities: { y30: number; y50: number },
  neverProbability: number,
  medianBreakEvenYear: number | null,
  finalMedianBalance: number,
  dominantLabel: string | null,
  horizon: number,
): string {
  const dominant = dominantLabel ? dominantLabel.toLowerCase() : 'the leading assumption';
  if (neverProbability > 0.9) {
    return `Almost no simulated path reached sustained break-even within ${horizon} years; the median path ended ${formatWater(Math.abs(finalMedianBalance))} M m³ short, with ${dominant} driving most of the spread.`;
  }
  if (medianBreakEvenYear === null) {
    return `No path crossed zero and stayed there through year ${horizon}; cumulative AI burden exceeded credited savings in every ensemble member.`;
  }
  if (neverProbability < 0.15) {
    return `Most paths reached sustained break-even around year ${medianBreakEvenYear} and stayed above zero to year ${horizon}; ${dominant} dominates the residual uncertainty.`;
  }
  return `The ensemble splits: ${Math.round((1 - neverProbability) * 100)}% of paths reach sustained break-even — median year ${medianBreakEvenYear} — while ${Math.round(neverProbability * 100)}% remain below zero at year ${horizon}, largely because of ${dominant}.`;
}
