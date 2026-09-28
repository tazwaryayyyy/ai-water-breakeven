# AI Water Break-Even

An interactive Monte Carlo simulator comparing cumulative AI water burden with water savings credited to AI-enabled interventions.

## What it is

Each run samples uncertain assumptions and estimates the share of simulated paths that reach sustained break-even within the selected horizon. A path reaches break-even when its cumulative balance becomes non-negative and stays there to the end of the horizon.

The implementation is in [artifacts/ai-water-break-even](artifacts/ai-water-break-even). Its defaults are illustrative assumptions, not measured inputs or an empirical forecast.

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

Controls cover AI growth, efficiency improvement, savings potential, adoption, realization, attribution, starting water use, horizon, run count, and random seed. Results include cumulative balance curves, uncertainty bands, break-even summaries, sensitivity rankings, and baseline/alternative scenario comparisons. The app exports JSON and CSV data and a PNG chart.

## Reproducibility

The Monte Carlo generator is seeded. The same configuration and seed reproduce the same results; changing either changes the sampled ensemble.

## Scope

This is a scenario-analysis demo. Its inputs are illustrative, and simulated probabilities describe sampled paths under those assumptions, not real-world outcomes.

## License

MIT. See [LICENSE](LICENSE).
