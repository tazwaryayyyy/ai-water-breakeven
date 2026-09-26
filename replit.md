# AI Water Break-Even

A standalone interactive Monte Carlo demonstration that lets people explore when illustrative AI-enabled water savings could offset illustrative AI water use.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)
- Frontend: React + Vite, Recharts, Tailwind CSS

## Where things live

- `artifacts/ai-water-break-even/src/simulation.ts` — seeded Monte Carlo engine, distributions, aggregation, break-even detection, sensitivity calculations, and scenario cases.
- `artifacts/ai-water-break-even/src/App.tsx` — the interactive scientific demonstration surface and export controls.
- `artifacts/ai-water-break-even/src/index.css` — the parchment/teal/amber instrument visual language.
- `artifacts/ai-water-break-even` — the deployable web artifact at `/`.

## Architecture decisions

- Simulation calculations are isolated from the UI and use a seeded PRNG so the same assumptions and seed reproduce the same model outputs.
- Sustained break-even counts only when cumulative net balance reaches zero or above and remains there through the end of the selected horizon.
- The app is frontend-only by design; it has no auth, database, external data, LLM calls, or research-repository dependency.
- Percentages and sensitivity rankings are derived from Monte Carlo runs; default values are labeled illustrative and are not research findings.
- Scenario comparison runs the same engine with baseline, more-savings-realized, and difficult-condition configurations.

## Product

- Users adjust burden, savings, adoption, attribution, horizon, run count, and seed assumptions.
- The app shows cumulative burden, cumulative savings, net balance, middle-50% and middle-90% uncertainty envelopes, break-even probabilities, distributions, scenario comparisons, sensitivity reruns, a deterministic explanation, and an expandable method view.
- Current results can be exported as CSV or JSON, and the main chart can be downloaded as PNG.

## User preferences

- Do not use generic “AI slop” components or dashboard styling; keep the experience chart-led, restrained, and scientifically honest.

## Gotchas

- Run the web artifact through its managed workflow so `PORT`, `BASE_PATH`, and preview routing are present.
- The app build emits a non-blocking Vite sourcemap warning from the scaffold tooltip component and a chunk-size warning; typecheck and build still pass.
- The Monte Carlo result object intentionally excludes runtime timing so exact seed reproducibility is not polluted by machine speed.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
