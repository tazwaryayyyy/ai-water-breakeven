# AI Water Break-Even

A production-grade Monte Carlo research simulator comparing cumulative AI water
burden with water savings credited to AI-enabled interventions. All computation
runs off the main thread in a dedicated Web Worker; the interface is an
editorial, Swiss-inspired research dashboard.

## What it is

Each run samples uncertain assumptions and estimates the share of simulated
paths that reach **sustained break-even** within the selected horizon. A path
breaks even at year T if and only if its cumulative net balance stays ≥ 0 from
T through the end of the horizon — found by scanning backwards for the last
negative year.

The implementation lives in [artifacts/ai-water-break-even](artifacts/ai-water-break-even).
Its defaults are illustrative assumptions, not measured inputs or an empirical
forecast.

## Architecture

```
artifacts/ai-water-break-even/src/
├── domain/
│   ├── math/
│   │   ├── prng.ts                # 32-bit xoshiro128** (SplitMix32 seed, Math.imul, no BigInt)
│   │   └── statistics.ts          # In-place typed-array sorts and quantile extraction
│   ├── model/
│   │   ├── types.ts               # Strict domain + worker wire-protocol types
│   │   └── simulation-engine.ts   # Vectorized, zero-allocation Monte Carlo engine
│   └── worker/
│       ├── simulation.worker.ts   # Worker entry: runs, sensitivity, scenarios
│       └── worker-client.ts       # Typed native postMessage bridge, abortable request IDs
├── components/
│   ├── bento/                     # BentoGrid, MetricTile, ProbabilityTile
│   ├── controls/                  # ParameterScrubber, ScenarioSelector
│   ├── visualization/             # MainBalanceChart, SensitivityTornado, DistributionChart
│   └── ui/                        # Button, Tile primitives
├── hooks/
│   ├── useSimulation.ts           # Worker lifecycle, debounced dispatch, progress
│   └── useExport.ts               # CSV / JSON / high-DPI PNG export
├── App.tsx
└── index.css                      # Tailwind v4 warm editorial theme
```

### Performance properties

- **Zero main-thread freezing.** Baseline, sensitivity probes (all 8
  parameters), and scenario comparisons run inside the worker over flat
  `Float64Array` / `Int32Array` matrices.
- **No RPC library.** The worker bridge uses native `postMessage` with
  Transferable buffers, incrementing request IDs, and a generation-token
  cancellation scheme: a new run supersedes an in-flight one within a single
  2,500-path chunk.
- **Fast PRNG.** xoshiro128** seeded by SplitMix32 — plain 32-bit
  `Math.imul` arithmetic, no BigInt in the hot loop — with Box–Muller
  normals, truncated-normal, and log-normal parameter sampling.
- **Zero-GC quantiles.** Year slices are sorted in place
  (`Float64Array.prototype.sort`) and read at the 5th/25th/50th/75th/95th
  percentiles; no buffer clones, no per-call allocations.
- **60 FPS scrubbing.** Slider drags coalesce through a 130 ms debounce into
  one worker dispatch per pause; charts render with animations off.

## Path equations

- Burden: `W_b(t) = W₀ · (1 + g_ai)^t · (1 − e_water)^t`
- Savings: `W_s(t) = S₀ · 1.022^t · (adoption · (1 − e^(−0.105 t))) · E_int · R · F_attr`

Both are evaluated by iterative compounding in the inner loop — algebraically
identical, with no `Math.pow` or `Math.exp` per year.

## Run locally

From the repository root:

```bash
npx pnpm install --frozen-lockfile
npx pnpm --dir artifacts/ai-water-break-even run dev
```

```bash
npx pnpm --dir artifacts/ai-water-break-even run build
npx pnpm --dir artifacts/ai-water-break-even run typecheck
```

## Inputs and outputs

Controls cover all eight model parameters plus horizon (10–80 years), run
count (250–20,000), and seed, with one-click presets (Reference Case, High AI
Burden, Aggressive Conservation, Delayed Adoption). Results include percentile
trajectories for burden, savings, and net balance; break-even year
distribution; sensitivity tornado; and Baseline / Accelerated Savings / High
Growth scenario comparison. The app exports full-ensemble CSV, reproducibility
JSON, and a 3× PNG of the main chart.

## Reproducibility

The Monte Carlo generator is seeded. The same configuration and seed reproduce
the same results bit-for-bit; sensitivity probes add deterministic
per-parameter seed offsets.

## Scope

This is a scenario-analysis tool. Its inputs are illustrative, and simulated
probabilities describe sampled paths under those assumptions, not real-world
outcomes.

## License

MIT. See [LICENSE](LICENSE).
