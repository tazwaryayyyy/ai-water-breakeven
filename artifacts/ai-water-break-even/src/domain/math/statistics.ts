/**
 * Zero-garbage quantile extraction for typed arrays.
 *
 * The engine keeps its matrices column-major per simulation; to read a year
 * slice we copy it into a reusable scratch buffer and sort that buffer
 * in place (`Float64Array.prototype.sort` is numeric and allocation-free),
 * then read interpolated quantiles off the sorted run. No slicing, no
 * cloning, no per-call arrays escape to the GC.
 */

/** Copy one year column (stride = horizon) of a simulation matrix into scratch. */
export function copyColumn(
  matrix: Float64Array,
  simulations: number,
  horizon: number,
  yearIndex: number,
  scratch: Float64Array,
): void {
  for (let sim = 0; sim < simulations; sim++) {
    scratch[sim] = matrix[sim * horizon + yearIndex];
  }
}

/**
 * Linearly interpolated quantile of an already-sorted ascending buffer.
 * `p` is in [0, 1]; uses the rank method index p·(n−1), matching the
 * classical Hyndman–Fan type 7 definition.
 */
export function sortedQuantile(sorted: Float64Array, length: number, p: number): number {
  if (length === 0) return 0;
  if (length === 1) return sorted[0];
  const index = p * (length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return sorted[lower];
  const weight = index - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

export interface QuantileBand {
  p5: number;
  p25: number;
  median: number;
  p75: number;
  p95: number;
}

/** Read the five summary quantiles off a sorted, ascending buffer. */
export function bandOfSorted(sorted: Float64Array, length: number): QuantileBand {
  return {
    p5: sortedQuantile(sorted, length, 0.05),
    p25: sortedQuantile(sorted, length, 0.25),
    median: sortedQuantile(sorted, length, 0.5),
    p75: sortedQuantile(sorted, length, 0.75),
    p95: sortedQuantile(sorted, length, 0.95),
  };
}

/** Median of an Int32Array using a scratch copy sorted in place. */
export function medianOfInt32(values: Int32Array, length: number, scratch: Int32Array): number {
  if (length === 0) return 0;
  scratch.set(values.subarray(0, length));
  const sorted = scratch.subarray(0, length);
  sorted.sort();
  const mid = length >> 1;
  return (length & 1) === 1 ? sorted[mid] : Math.round((sorted[mid - 1] + sorted[mid]) / 2);
}
