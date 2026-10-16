/**
 * Fast 32-bit PRNG for Monte Carlo simulation.
 *
 * Seeding uses SplitMix32; the generator is xoshiro128**, the canonical
 * 32-bit adaptation of Xoroshiro128** (Blackman & Vigna, 2018). Everything
 * runs on standard JavaScript 32-bit integers via `Math.imul` — no BigInt,
 * no allocation, so the inner loop stays monomorphic under V8 and sustains
 * hundreds of millions of draws per second.
 */
export class FastPRNG {
  private s0: number;
  private s1: number;
  private s2: number;
  private s3: number;

  constructor(seed: number) {
    let s = (seed >>> 0) || 0x9e3779b9;
    const splitmix = (): number => {
      s = (s + 0x9e3779b9) | 0;
      let z = s;
      z = Math.imul(z ^ (z >>> 16), 0x21f0aaad);
      z = Math.imul(z ^ (z >>> 15), 0x735a2d97);
      return (z ^ (z >>> 15)) >>> 0;
    };
    // Reject the all-zero state, which is degenerate for xoshiro.
    this.s0 = splitmix();
    this.s1 = splitmix();
    this.s2 = splitmix();
    this.s3 = splitmix();
    if ((this.s0 | this.s1 | this.s2 | this.s3) === 0) this.s0 = 0x9e3779b9;
  }

  /** Raw 32-bit unsigned integer draw. */
  public nextUint32(): number {
    const s1 = this.s1;
    // xoshiro128** output: rotl(s1 * 5, 7) * 9
    const m = Math.imul(s1, 5);
    const result = Math.imul((m << 7) | (m >>> 25), 9);

    const t = s1 << 9;
    this.s2 ^= this.s0;
    this.s3 ^= s1;
    this.s1 ^= this.s2;
    this.s0 ^= this.s3;
    this.s2 ^= t;
    this.s3 = (this.s3 << 11) | (this.s3 >>> 21);

    return result >>> 0;
  }

  /** Uniform draw in [0, 1). */
  public nextFloat(): number {
    return this.nextUint32() / 4294967296.0;
  }

  /** Standard normal draw via the Box–Muller transform. */
  public nextNormal(mean = 0, stdDev = 1): number {
    let u1 = this.nextFloat();
    while (u1 <= 1e-15) u1 = this.nextFloat();
    const u2 = this.nextFloat();
    const z0 = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
    return mean + z0 * stdDev;
  }

  /**
   * Truncated normal draw, rejection-sampled with a bounded retry budget.
   * Falls back to the clamped mean so the sampler can never loop forever.
   */
  public nextTruncatedNormal(mean: number, stdDev: number, min: number, max: number): number {
    for (let i = 0; i < 20; i++) {
      const v = this.nextNormal(mean, stdDev);
      if (v >= min && v <= max) return v;
    }
    return Math.min(max, Math.max(min, mean));
  }
}
