# AI Water Break-Even

Monte Carlo scenario model examining the conditions under which water benefits attributed to AI would offset the water used by AI compute. The two benefit pathways are desalination, where cost and energy gains add supply, and solar-driven food production that displaces agricultural crop water use.

Full formulation, equations, definitions, and limitations: [docs/model.md](docs/model.md).  
Step-by-step reproduction guide: [docs/reproducibility.md](docs/reproducibility.md).

> **Status Notice:** Deployment probabilities (`p_*`), counterfactual AI attribution shares (`alpha_*`), rebound factors (`rho_*`), and desalination efficiency gains (`theta_*`) remain exploratory placeholders (`PLACEHOLDER` in `data/parameters.csv`). Unconditional joint probabilities (e.g. break-even across all simulation runs) must not be cited as real-world forecasts. The analytical findings of this repository are the conditional-on-deployment trajectories, two-parameter break-even thresholds, structural knockouts, and sensitivity diagnostics. Sourced baseline inputs: global AI water baseline (Li et al., 2025), global agricultural blue-water consumption baseline `A` (Chukalla et al., 2025; Mekonnen and Hoekstra, 2011), and global desalinated water output `D` (Jones et al., 2019). Source-informed assumptions (not measured empirical rates): `g_global`, `G_global`, `g2_global`, `phi_solar_food`, `r_solar_food_consumption`, `L_solar_food`, and `R_solar_food`.

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

# Execute headline consumption-basis simulation (N=100,000, T=50)
ai-water-breakeven run --region global --basis consumption --samples 100000 --horizon 50 --out-dir results
```

To reproduce all runnable scenarios, figures, knockouts, and threshold maps:

```bash
ai-water-breakeven reproduce --out-dir results
```

For simulation outputs and parameter sensitivity rankings, see `summary.json`, `summary.csv`, and `sourcing_priority.csv`.

## Model Formulation

### Cumulative Water Balance

The cumulative net freshwater balance $N(t)$ at year $t \in [1, T]$ is:

$$N(t) = \sum_{\tau=1}^t \left( \sum_{i} B_i(\tau) - C(\tau) \right)$$

where $C(t)$ is annual operational compute water requirement and $B_i(t)$ is attributable water benefit from technology pathway $i$.

The **sustained break-even year** $t^*$ is defined as the earliest year after which the cumulative net balance remains non-negative for the remainder of the horizon:

$$t^* = \min \{ t \in [1, T] : N(\tau) \ge 0 \quad \forall \tau \in [t, T] \}$$

### Calendar-Year Mapping

- **Baseline Reference Year:** **2027** ($t = 0$).
- **Projection Steps:** $t = 1$ through $t = 50$ represent calendar years **2028 through 2077** (50 annual compounding steps following the baseline). 2027 is the baseline reference year, followed by 50 discrete annual increments.

### Operational Cost Trajectory

Data center water demand follows a two-phase compounding growth path reflecting rapid near-term scaling followed by a long-term transition rate:

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
- $\alpha_i \in [0, 1]$: Constant fractional credit attributed to AI (constant attribution assumption; acceleration dynamics noted as future work).
- $\rho_i \ge 0$: Rebound effect consumption fraction.
- $\text{ramp}_i(t)$: Piecewise linear adoption ramp starting after lag $L_i$ and taking $R_i$ years to reach full deployment.
- **Desalination:** Gross benefit $D \cdot \theta$, where $D$ is global desalinated output (m³/yr, Jones et al. 2019) and $\theta$ is the fractional increase in output from cost and energy improvements from all causes. The AI share is applied separately through $\alpha$. Desalination adds supply; it does not reduce consumption (explicit supply-credit interpretation).
- **Solar food:** Gross benefit $\phi \cdot A \cdot (1 - r)$, where $A$ is baseline agricultural crop blue-water consumption ($A \approx 1.08 \times 10^{12} \text{ m}^3/\text{yr}$ from Chukalla et al. 2025 and Mekonnen & Hoekstra 2011), $\phi$ is the share of $A$ displaced, and $r$ is the water intensity of the solar food system relative to conventional production (0 = none, 1 = equal).

## Accounting Rules and Scope Safeguards

1. **Physical Basis Consistency:**
   - `withdrawal`: Total volume extracted from surface/groundwater sources.
   - `consumption`: Volume evaporated or permanently incorporated into products.
   - Mixing withdrawal and consumption within a single scenario is disallowed.
   - The default configuration file (`configs/base.toml`) selects `global` + `withdrawal`, where agricultural withdrawal rows carry `MISSING` sources. The verified headline research findings use `--region global --basis consumption`.

2. **Regional Scopes:**
   - `global`: Fully runnable. Combines Scope 1 and Scope 2 operational water from Li et al. (2025) with global benefit pathways.
   - `us`: Reserved and non-runnable. US data center consumption parameters are included in `data/parameters.csv` (17.4B gallons direct, 211B gallons indirect electricity for 2023, LBNL-2001637), but US-specific benefit pathways are not cataloged. Comparing US costs against global benefits is blocked during validation.

3. **Dominance Auditing:**
   - Any parameter with $|PRCC| > 0.85$ trips a `dominance_warning` in `sourcing_priority.csv` and triggers a console notice.
   - `breakeven_dominance_warning` flags rows (including realized deployment draws) with absolute break-even correlation $> 0.85$.
   - Consult `abs_corr_breakeven_given_solar_food` for timing sensitivity among deployed runs.

## CLI Reference

| Command | Flags | Defaults | Description |
| :--- | :--- | :--- | :--- |
| `validate` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}]` | `data/parameters.csv`, `configs/base.toml` | Checks parameter schema bounds, physical basis consistency, and unverified source flags. `--strict` rejects unverified inputs. |
| `run` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES] [--horizon HORIZON]` | `--out-dir results`, `--samples 100000`, `--horizon 50` | Executes Monte Carlo simulation; writes `summary.csv`, `prcc.csv`, `sourcing_priority.csv`, trajectory files, and `run_metadata.json`. |
| `figures` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES] [--horizon HORIZON]` | `--out-dir results`, `--samples 100000`, `--horizon 50` | Generates publication figures (`fig1` through `fig5`, `fig8`) in PNG (300 DPI) and SVG. |
| `knockouts` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES] [--horizon HORIZON]` | `--out-dir results`, `--samples 100000`, `--horizon 50` | Runs Common-Random-Number structural knockouts; produces `fig6_knockouts`. |
| `threshold` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--x X] [--y Y] [--horizon HORIZON] [--eval-horizon EVAL_HORIZON] [--grid GRID] [--n-per-cell N_PER_CELL] [--x-range LO HI] [--y-range LO HI] [--log] [--conditional {none,solar_food,desal,both}]` | `--out-dir results`, `--x g_global`, `--y phi_solar_food`, `--horizon 30`, `--eval-horizon 50`, `--grid 15`, `--n-per-cell 5000`, `--log false`, `--conditional none` | Evaluates 2D break-even parameter response surfaces over shared base draws; produces `fig7_threshold_map`. Uses `--n-per-cell` for sample size per grid cell (`--samples` is rejected). |
| `reproduce` | `[--parameters PARAMETERS] [--config CONFIG] [--strict] [--allow-mixed-basis] [--region {global,us}] [--basis {withdrawal,consumption}] [--out-dir OUT_DIR] [--samples SAMPLES] [--horizon HORIZON] [--threshold-x X] [--threshold-y Y] [--threshold-horizon HORIZON] [--threshold-eval-horizon EVAL_HORIZON] [--threshold-grid GRID] [--threshold-n-per-cell N_PER_CELL] [--threshold-x-range LO HI] [--threshold-y-range LO HI] [--threshold-log] [--threshold-conditional {none,solar_food,desal,both}]` | `--out-dir results`, `--samples 100000`, `--horizon 50` | Runs complete reproduction pipeline across runnable scenario combinations, exposes all threshold controls, and records manifests. |

## Generated Artifacts

| File | Description |
| :--- | :--- |
| `summary.json` / `.csv` | Horizon break-even probabilities, Wilson confidence intervals, MCSE, $N(T)$ quantiles, benefit shares, and disclosures. |
| `prcc.csv` | Partial Rank Correlation Coefficients against cumulative net balance $N(T)$. |
| `tornado.csv` | One-at-a-time low/high sensitivity on final net balance $N(T)$, ranked by swing, with deterministic distribution-midpoint baselines (no Bernoulli draws). |
| `sourcing_priority.csv` | Parameters ranked by absolute PRCC with source traceability, confidence tiers, dominance warnings, and break-even correlations conditional on solar-food deployment (`abs_corr_breakeven_given_solar_food`). |
| `conditions.csv` | Parameter medians and IQRs stratified by runs achieving sustained break-even by the configured reporting horizon (default 30). |
| `cost_trajectory.csv` | Cost percentiles $C(t)$, compounding ratios $C(t)/C(0)$, and explicit calendar years at benchmark years (5, 10, 25, 50). |
| `net_balance_by_horizon.csv` | Cumulative balance $N(t)$ percentiles and calendar years across comparison horizons. |
| `knockouts.csv` | Break-even probabilities across deterministic knockout scenarios. |
| `conditional.csv` | Break-even probabilities with Wilson intervals, never-share, and break-even year percentiles among runs where solar_food, desal, or either pathway deploys. |
| `threshold_map.csv` | Grid of break-even probabilities across two chosen parameter ranges. |
| `run_metadata.json` | Execution metadata including Git commit hash, Git tag, working tree cleanliness, execution timestamp, Python and package versions, seed, sample counts, horizons, and input SHA-256 hashes. |
| `reproduce_status.csv` | Per region/basis combination: ran or skipped, with missing rows for skipped combinations. |
| `reproduce_manifest.json` | Ran and skipped combinations with their output directories and metadata. |
| `fig1_breakeven_dist`, `fig2_p_breakeven_horizon`, `fig3_net_balance_fan`, `fig4_tornado`, `fig5_scope_comparison`, `fig6_knockouts`, `fig7_threshold_map`, `fig8_breakeven_given_solar_food` (`.png` and `.svg`) | Complete publication figure set in PNG (300 DPI) and vector SVG. |

## Limitations

- **Spatial Aggregation:** Balances are evaluated globally. The model does not capture watershed-level hydrological stress or local basin extraction constraints.
- **Unweighted Scarcity:** All cubic meters are treated equally regardless of local aquifer depletion or regional water stress indices.
- **Scope 3 Excluded:** Embodied water from semiconductor manufacturing, hardware supply chains, and facility construction is omitted.
- **Post-2035 Uncertainty:** Growth trajectories past 2035 have no empirical backing and serve as exploratory scenario bounds.
- **Static Baselines:** Global agricultural water demand ($A$) and desalinated output ($D$) are held static without dynamic climate or demographic feedback.
- **Independent Sampling:** Inputs are sampled independently (no correlation structure).
- **No Discounting:** No discounting is applied.
- **Attribution Shares:** Attribution shares (alpha) are constant modeling assumptions, not empirical measurements.
- **Deployment Bound:** Each pathway deploys or does not (one Bernoulli draw per run), so the break-even probability cannot exceed the probability that at least one pathway deploys.
- **Desalination Supply:** Desalination adds supply and does not reduce consumption; on the consumption basis its contribution is a supply credit.
- **Timing Assumptions:** Solar-food lag and ramp (`L_solar_food`, `R_solar_food`) are assumptions informed by historical diffusion of energy technologies.

Full limitations discussion: [docs/limitations.md](docs/limitations.md).

## Citation

```bibtex
@software{ai_water_breakeven_2026,
  title  = {AI Water Break-Even: A Monte Carlo Scenario Model},
  author = {Tazwar},
  year   = {2026},
  version= {0.3.0},
  url    = {https://github.com/tazwaryayyyy/ai-water-breakeven}
}
```

Primary benchmarks:
- Li, P., Yang, J., Islam, M. A., & Ren, S. (2025). "Making AI Less 'Thirsty': Uncovering and Addressing the Secret Water Footprint of AI Models." *Communications of the ACM*, 68(7), 54–61. [DOI: 10.1145/3724499](https://doi.org/10.1145/3724499).
- Jones, E., Qadir, M., van Vliet, M. T. H., Smakhtin, V., & Kang, S. (2019). "The state of desalination and brine production: A global outlook." *Science of The Total Environment*, 657, 1343–1356. [DOI: 10.1016/j.scitotenv.2018.12.076](https://doi.org/10.1016/j.scitotenv.2018.12.076).

## License

MIT License. Copyright (c) 2026 Tazwar. See [LICENSE](LICENSE) for details.
