# AI Water Break-Even

Monte Carlo scenario model of the conditions under which water benefits attributed to AI would offset the water used by AI compute. The two benefit pathways are desalination, where cost and energy gains add supply, and solar-driven food production that displaces crop water use.

Equations, definitions and limitations: [docs/model.md](docs/model.md).

> Status: most inputs are PLACEHOLDER or MISSING in `data/parameters.csv`. Outputs are illustrative, not findings. Do not cite them. Sourced: the global AI water baseline (Li et al. 2025) and the agricultural blue-water baseline `A` on the consumption basis. Assumptions informed by sources, not measured rates: `g_global`, `G_global`, `g2_global`, `phi_solar_food`, `r_solar_food_consumption`, `L_solar_food` and `R_solar_food`. Deployment probabilities, attribution shares, rebound and all desalination inputs are placeholders.

## Quickstart

### Installation

Requires Python >= 3.11.

```bash
git clone https://github.com/tazwaryayyyy/ai-water-breakeven.git
cd ai-water-breakeven
pip install -e .
```

To install development dependencies (testing, linting):

```bash
pip install -e ".[dev]"
```

### Run Simulation

Validate parameter distributions and run a 100,000-draw Monte Carlo simulation over a 50-year horizon:

```bash
# Validate input schema and physical consistency
ai-water-breakeven validate

# Execute baseline simulation (global withdrawal, N=100,000, T=50)
ai-water-breakeven run --out-dir results --samples 100000 --horizon 50
```

To reproduce all runnable scenarios, figures, knockouts, and threshold maps:

```bash
ai-water-breakeven reproduce --out-dir results
```

For illustrative simulation outputs and parameter sensitivity rankings, see `summary.json` and `sourcing_priority.csv`.

## Model Formulation

### Cumulative Water Balance

The cumulative net freshwater balance $N(t)$ at year $t \in [1, T]$ is:

$$N(t) = \sum_{\tau=1}^t \left( \sum_{i} B_i(\tau) - C(\tau) \right)$$

where $C(t)$ is annual operational compute water requirement and $B_i(t)$ is attributable water benefit from technology pathway $i$.

The **sustained break-even year** $t^*$ is defined as the earliest year after which the cumulative net balance remains non-negative for the remainder of the horizon:

$$t^* = \min \{ t \in [1, T] : N(\tau) \ge 0 \quad \forall \tau \in [t, T] \}$$

### Operational Cost Trajectory

Data center water demand follows a two-phase growth path reflecting rapid near-term scaling followed by a long-term transition rate:

$$C(t) = (W_{\text{direct}} + k \cdot W_{\text{indirect}}) \cdot (1 + g_1)^{\min(t, G_1)} \cdot (1 + g_2)^{\max(t - G_1, 0)}$$

- $W_{\text{direct}}$: Direct operational water volume (m³/yr). For global scenarios, direct rows represent combined Scope 1 (on-site cooling) and Scope 2 (grid electricity) from Li et al. (2025).
- $k \in [0, 1]$: Scope switch for indirect electricity water (applies to US scenarios with separated accounting; $W_{\text{indirect}} = 0$ for global).
- $g_1$: Phase 1 annual growth rate (informed by IEA 2025 and data center power projections). Range in `data/parameters.csv`.
- $G_1$: Phase 1 duration in years. Range in `data/parameters.csv`.
- $g_2$: Phase 2 long-term annual growth rate. Range in `data/parameters.csv`.

### Technology Benefit Pathways

For each benefit pathway $i \in \{\text{desal}, \text{solar food}\}$:

$$B_i(t) = s_i \cdot \alpha_i \cdot \text{Gross}_i \cdot \text{ramp}_i(t) \cdot (1 - \rho_i)$$

- $s_i \sim \text{Bernoulli}(p_i)$: Binary deployment success flag.
- $\alpha_i \in [0, 1]$: Fractional credit attributed to AI.
- $\rho_i \ge 0$: Rebound effect consumption fraction.
- $\text{ramp}_i(t)$: Piecewise linear adoption ramp starting after lag $L_i$ and taking $R_i$ years to reach full deployment.
- Desalination: gross benefit $D$ times $\theta$, where $D$ is global desalinated output (m3/yr) and $\theta$ is the fractional increase in that output from cost and energy improvements, from all causes. The AI share of the benefit is applied separately through $\alpha$. Desalination adds supply; it does not reduce consumption.
- Solar food: gross benefit $\phi$ times $A$ times $(1 - r)$, where $A$ is baseline agricultural water use on the chosen basis (crop blue-water consumption, or irrigation withdrawal), $\phi$ is the share of $A$ displaced, and $r$ is the water intensity of the solar-driven food system relative to conventional production (0 = none, 1 = equal).

## Accounting Rules and Scope Safeguards

1. **Physical Basis Consistency:**
   - `withdrawal`: Total volume extracted from water sources.
   - `consumption`: Volume evaporated or permanently incorporated into products. If a pathway's sampled gross benefit is identically zero (for example, an unset sentinel input), the model detects it and outputs a `basis_notice`; with the current inputs no pathway is zero.
   - Mixing withdrawal and consumption within a single scenario is disallowed by default.

2. **Regional Scopes:**
   - `global`: Fully runnable. Combines Scope 1 and Scope 2 operational water from Li et al. (2025) with global efficiency pathways.
   - `us`: Reserved and non-runnable. US data center consumption parameters are included in `data/parameters.csv` (17.4B gallons direct, 211B gallons indirect electricity for 2023, LBNL-2001637), but US-specific benefit pathways are not cataloged. Comparing US costs against global benefits is blocked during validation.

3. **Dominance Auditing:**
   - During sensitivity analysis, any parameter with absolute Partial Rank Correlation Coefficient $|PRCC| > 0.85$ trips a `dominance_warning` in `sourcing_priority.csv` and triggers a console warning during `ai-water-breakeven run`.

## CLI Reference

Common defaults are `--parameters data/parameters.csv`, `--config configs/base.toml`, `--region None` and `--basis None` (the config selects `global` and `withdrawal`), and false `--strict` and `--allow-mixed-basis`. For `--samples` and run `--horizon`, `None` selects the config values `N = 100000` and `T = 50`.

| Command | Flags | Defaults | Description |
| :--- | :--- | :--- | :--- |
| `validate` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}]` | Common defaults. | Checks parameter schema bounds, physical basis consistency, and unverified source flags. |
| `run` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES] [--horizon HORIZON]` | `--out-dir results`; `--samples None` (100000); `--horizon None` (50). | Executes Monte Carlo simulation; writes `summary.csv`, `prcc.csv`, `sourcing_priority.csv`, and trajectory files. |
| `figures` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES]` | `--out-dir results`; `--samples None` (100000). | Generates publication figures (`fig1` through `fig5`, `fig8`) in PNG (300 DPI) and SVG. |
| `knockouts` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES] [--horizon HORIZON]` | `--out-dir results`; `--samples None` (100000); `--horizon None` (50). | Runs Common-Random-Number structural knockouts (e.g., zero rebound, no delay, flat cost); produces `fig6_knockouts`. |
| `threshold` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES] [--x X] [--y Y] [--horizon HORIZON] [--grid GRID] [--n-per-cell N_PER_CELL] [--x-range LO HI] [--y-range LO HI] [--log]` | `--out-dir results`; `--samples None`; `--x g_global`; `--y phi_solar_food`; `--horizon 30`; `--grid 15`; `--n-per-cell 5000`; `--x-range None`; `--y-range None`; `--log` false. | Evaluates 2D break-even parameter response surfaces over shared base draws; produces `fig7_threshold_map`. Optional range overrides and log-spacing. |
| `reproduce` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES] [--horizon HORIZON]` | `--out-dir results`; `--samples None` (100000); `--horizon None` (50). | Runs complete pipeline across all runnable scenario configurations and records run manifests. |

## Generated Artifacts

| File | Description |
| :--- | :--- |
| `summary.json` / `.csv` | Horizon break-even probabilities, Wilson confidence intervals, MCSE, $N(T)$ quantiles, benefit shares, and notice disclosures. |
| `prcc.csv` | Partial Rank Correlation Coefficients of continuous parameters against cumulative net balance $N(T)$. |
| `tornado.csv` | One-at-a-time low/high sensitivity of the final net balance $N(T)$, ranked by swing. |
| `sourcing_priority.csv` | Parameters ranked by absolute PRCC with source traceability, confidence tiers, and dominance warnings. |
| `conditions.csv` | Parameter medians and IQRs stratified by runs achieving sustained break-even by the configured conditions_horizon (default 30). |
| `cost_trajectory.csv` | Cost percentiles $C(t)$ and compounding ratios $C(t)/C(0)$ at benchmark years (5, 10, 25, 50). |
| `net_balance_by_horizon.csv` | Cumulative balance $N(t)$ percentiles across comparison horizons. |
| `knockouts.csv` | Break-even probabilities across deterministic knockout scenarios. |
| `conditional.csv` | Break-even probabilities with Wilson intervals, never-share, and break-even year percentiles among runs where solar_food, desal, or either pathway deploys. Rows do not isolate a pathway's contribution (see docs/model.md). |
| `threshold_map.csv` | Grid of break-even probabilities across two chosen parameter ranges. |
| `run_metadata.json` | Execution metadata including git commit hash, timestamp, Python version, random seed, and parameter SHA-256 hashes. |
| `reproduce_status.csv` | Per region/basis combination: ran or skipped, with missing rows for skipped combinations. |
| `reproduce_manifest.json` | Ran and skipped combinations with their output directories and the publication notice. |
| `fig1_breakeven_dist`, `fig2_p_breakeven_horizon`, `fig3_net_balance_fan`, `fig4_tornado`, `fig5_scope_comparison`, `fig6_knockouts`, `fig7_threshold_map`, `fig8_breakeven_given_solar_food` (`.png` and `.svg`) | Break-even year distribution; break-even probability by horizon; net balance fan chart; one-at-a-time tornado; scope comparison ($k = 0$ vs $k = 1$); knockout probabilities; two-parameter threshold map; break-even distribution given solar-food deployment. |

## Limitations

- **Spatial Aggregation:** Balances are evaluated globally. The model does not capture watershed-level hydrological stress or local basin extraction constraints.
- **Unweighted Scarcity:** All cubic meters are treated equally regardless of local aquifer depletion or regional water stress indices.
- **Scope 3 Excluded:** Embodied water from semiconductor manufacturing, hardware supply chains, and facility construction is omitted.
- **Post-2035 Uncertainty:** Growth trajectories past 2035 have no empirical backing and serve as exploratory scenario bounds.
- **Static Baselines:** Global agricultural water demand ($A$) and desalinated output ($D$) are held static without dynamic climate or demographic feedback.
- **Independent Sampling:** Inputs are sampled independently (no correlation structure).
- **No Discounting:** No discounting is applied.
- **Attribution Shares:** Attribution shares (alpha) are modeling assumptions, not measurements.
- **Deployment Bound:** Each pathway deploys or does not (one Bernoulli draw per run), so the break-even probability cannot exceed the probability that at least one pathway deploys; use `conditional.csv` for results given deployment.
- **Desalination Supply:** Desalination adds supply and does not reduce consumption, so on the consumption basis its contribution is a supply credit, separable with the `desal_only` and `solar_food_only` knockouts.
- **Timing Assumptions:** The solar-food lag and ramp (`L_solar_food`, `R_solar_food`) are assumptions informed by historical diffusion of energy technologies, which may not transfer to a food technology.

Longer prose version for the paper: [docs/limitations.md](docs/limitations.md).

## Citation

```bibtex
@software{ai_water_breakeven_2026,
  title  = {AI Water Break-Even: A Monte Carlo Scenario Model},
  author = {Tazwar},
  year   = {2026},
  url    = {https://github.com/tazwaryayyyy/ai-water-breakeven}
}
```

Primary AI water benchmark:
- Li, P., Yang, J., Islam, M. A., & Ren, S. (2025). "Making AI Less 'Thirsty': Uncovering and Addressing the Secret Water Footprint of AI Models." *Communications of the ACM*, 68(7), 54–61. [DOI: 10.1145/3724499](https://doi.org/10.1145/3724499). Preprint: [arXiv:2304.03271](https://doi.org/10.48550/arXiv.2304.03271).

## License

MIT License. Copyright (c) 2026 Tazwar. See [LICENSE](LICENSE) for details.
