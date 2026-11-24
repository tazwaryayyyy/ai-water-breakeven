# Reproducibility Guide: AI Water Break-Even Model

This document specifies the exact environment, execution sequence, and parameter controls required to reproduce the headline results and figures for version `v0.3.0`.

## 1. Environment and System Requirements

- **Python Version:** 3.11 or 3.12 (also tested on 3.13)
- **Dependencies:**
  - `numpy >= 1.26.0`
  - `scipy >= 1.11.0`
  - `pandas >= 2.1.0`
  - `matplotlib >= 3.8.0`
- **Optional Development Dependencies:**
  - `pytest >= 7.4.0`
  - `ruff >= 0.1.0`

### Installation

Clone the repository and check out the exact release used to generate the archived results:

```bash
git clone https://github.com/tazwaryayyyy/ai-water-breakeven.git
cd ai-water-breakeven

git fetch --tags
git checkout --detach v0.3.0

git rev-parse HEAD
```

Expected commit:

```text
c47b2af18f5e33758c22556b2f3ebc9c7749f651
```

Install the project and development dependencies:

```bash
pip install -e ".[dev]"
```

Verify tests and linting before proceeding:

```bash
ruff check .
ruff format --check .
pytest -v
```
---

## 2. Scientific Framing and Parameter Basis

- **Headline Analysis Basis:** `region=global`, `basis=consumption`.
- **Default CLI Configuration:** The default configuration file (`configs/base.toml`) defaults to `region="global"` and `basis="withdrawal"`. Because the agricultural denominator rows for withdrawal (`A_solar_food`, `r_solar_food`) are unverified placeholders, the headline research findings use explicit consumption arguments:
  ```bash
  --region global --basis consumption
  ```
- **Global Compute Water Footprint:** Evaluates combined Scope 1 (on-site cooling) and Scope 2 (grid electricity) from Li et al. (2025). Indirect electricity water is not counted twice (`W_indirect_global = 0`).
- **Agricultural Denominator:** Baseline blue-water crop consumption ($A \approx 1.08 \times 10^{12} \text{ m}^3/\text{yr}$) from Chukalla et al. (2025) and Mekonnen & Hoekstra (2011), not total freshwater withdrawal.
- **Desalination Output:** Supply-credit interpretation based on Jones et al. (2019) ($D \approx 35 \times 10^9 \text{ m}^3/\text{yr}$ mode). Desalination adds supply; it does not reduce consumption.
- **Calendar-Year Interpretation:**
  - Baseline reference year: **2027** ($t = 0$).
  - Evaluated steps: $t = 1$ through $t = 50$ represent calendar years **2028 through 2077** (50 annual compounding steps following the baseline).
- **Sampling:** Independent Latin Hypercube Sampling (LHS) across all continuous distributions with pseudo-random seed **42**.
- **Sample Counts:**
  - Monte Carlo runs: $N = 100,000$ draws.
  - Threshold parameter grids: $15 \times 15$ cells, with $n = 5,000$ Latin Hypercube draws per cell ($1,125,000$ total evaluations per grid).

---

## 3. Reproduction Pipeline: Step-by-Step Commands

### A. Headline Monte Carlo Simulation

Executes 100,000 simulation runs over a 50-year horizon ($T = 50$, evaluating 2028–2077):

```bash
ai-water-breakeven run \
  --region global \
  --basis consumption \
  --samples 100000 \
  --horizon 50 \
  --out-dir results_final_v0.3.0/consumption/run
```

Outputs generated:
- `summary.json` & `summary.csv`: Break-even probabilities, Wilson 95% confidence intervals, Monte Carlo standard errors, percentiles of $N(T)$, and pathway benefit shares.
- `conditional.csv`: Break-even statistics conditioned on pathway deployment (`solar_food`, `desal`, `any`).
- `sourcing_priority.csv`: PRCC rankings, break-even correlations (`abs_corr_breakeven`), conditional timing correlations (`abs_corr_breakeven_given_solar_food`), and dominance flags.
- `prcc.csv`: Partial Rank Correlation Coefficients against terminal net balance $N(50)$.
- `tornado.csv`: One-at-a-time sensitivity swings evaluated against deterministic distribution midpoints.
- `conditions.csv`: Parameter medians and IQRs stratified by break-even success by year 30 ($t = 30$, calendar year 2057).
- `cost_trajectory.csv`: Compounding cost percentiles and calendar years ($t=5, 10, 25, 50 \implies 2032, 2037, 2052, 2077$).
- `net_balance_by_horizon.csv`: Cumulative balance percentiles by comparison horizon.
- `run_metadata.json`: Execution metadata, environment versions, Git commit, and input SHA-256 hashes.

### B. Publication Figures

Generates publication figures (`fig1` through `fig5`, `fig8`) in 300 DPI PNG and vector SVG:

```bash
ai-water-breakeven figures \
  --region global \
  --basis consumption \
  --samples 100000 \
  --horizon 50 \
  --out-dir results_final_v0.3.0/consumption/figures
```

### C. Common-Random-Number Knockout Scenarios

Executes all nine structural knockout scenarios against the shared Latin Hypercube base draw:

```bash
ai-water-breakeven knockouts \
  --region global \
  --basis consumption \
  --samples 100000 \
  --horizon 50 \
  --out-dir results_final_v0.3.0/consumption/knockouts
```

Outputs:
- `knockouts.csv`
- `fig6_knockouts.png` and `fig6_knockouts.svg`
- `run_metadata.json`

### D. Threshold Maps: Attribution vs. Displaced Water

Evaluates response surface across $\alpha_{\text{solar food}} \in [0.001, 0.5]$ and $\phi_{\text{solar food}} \in [0.001, 0.13]$ (logarithmic spacing, $15 \times 15$ grid, 5,000 draws/cell, reporting horizon = 30 yr, evaluation horizon = 50 yr):

#### 1. Joint Pathway Model:
```bash
ai-water-breakeven threshold \
  --region global \
  --basis consumption \
  --x alpha_solar_food \
  --y phi_solar_food \
  --x-range 0.001 0.5 \
  --y-range 0.001 0.13 \
  --log \
  --horizon 30 \
  --eval-horizon 50 \
  --grid 15 \
  --n-per-cell 5000 \
  --out-dir results_final_v0.3.0/consumption/threshold_attribution_joint
```

#### 2. Solar-Food-Only Conditional Model ($p_{\text{desal}} = 0$, conditional on solar food deployment):
```bash
ai-water-breakeven threshold \
  --parameters results_final_v0.3.0/parameter_variants/parameters_solar_food_only.csv \
  --region global \
  --basis consumption \
  --x alpha_solar_food \
  --y phi_solar_food \
  --x-range 0.001 0.5 \
  --y-range 0.001 0.13 \
  --log \
  --horizon 30 \
  --eval-horizon 50 \
  --grid 15 \
  --n-per-cell 5000 \
  --conditional solar_food \
  --out-dir results_final_v0.3.0/consumption/threshold_attribution_solar_food_only
```

### E. Threshold Maps: Deployment Lag vs. Ramp Duration

Evaluates response surface across $L_{\text{solar food}} \in [0, 30]$ years and $R_{\text{solar food}} \in [0, 45]$ years (linear spacing, $15 \times 15$ grid, 5,000 draws/cell, reporting horizon = 30 yr, evaluation horizon = 50 yr):

#### 1. Joint Pathway Model:
```bash
ai-water-breakeven threshold \
  --region global \
  --basis consumption \
  --x L_solar_food \
  --y R_solar_food \
  --x-range 0.0 30.0 \
  --y-range 0.0 45.0 \
  --horizon 30 \
  --eval-horizon 50 \
  --grid 15 \
  --n-per-cell 5000 \
  --out-dir results_final_v0.3.0/consumption/threshold_timing_joint
```

#### 2. Solar-Food-Only Conditional Model ($p_{\text{desal}} = 0$, conditional on solar food deployment):
```bash
ai-water-breakeven threshold \
  --parameters results_final_v0.3.0/parameter_variants/parameters_solar_food_only.csv \
  --region global \
  --basis consumption \
  --x L_solar_food \
  --y R_solar_food \
  --x-range 0.0 30.0 \
  --y-range 0.0 45.0 \
  --horizon 30 \
  --eval-horizon 50 \
  --grid 15 \
  --n-per-cell 5000 \
  --conditional solar_food \
  --out-dir results_final_v0.3.0/consumption/threshold_timing_solar_food_only
```

### F. Timing Scenarios (Fast, Central, Slow)

Evaluated under two model formulations:
1. **Joint Pathway Timing:** Standard deployment probabilities.
2. **Solar-Food-Only Timing:** $p_{\text{desal}} = 0$, evaluating the `solar_food` row of `conditional.csv` for probability of break-even conditional on deployment.

- **Fast Scenario:** $L = 7 \text{ yr}$, $R = 10 \text{ yr}$ (fixed).
- **Central Scenario:** $L = 19 \text{ yr}$, $R = 25 \text{ yr}$ (fixed).
- **Slow Scenario:** $L = 30 \text{ yr}$, $R = 45 \text{ yr}$ (fixed).

Commands:
```bash
# Joint timing runs
ai-water-breakeven run --parameters results_final_v0.3.0/parameter_variants/parameters_timing_fast.csv --region global --basis consumption --samples 100000 --horizon 50 --out-dir results_final_v0.3.0/consumption/timing_fast_joint
ai-water-breakeven run --parameters results_final_v0.3.0/parameter_variants/parameters_timing_central.csv --region global --basis consumption --samples 100000 --horizon 50 --out-dir results_final_v0.3.0/consumption/timing_central_joint
ai-water-breakeven run --parameters results_final_v0.3.0/parameter_variants/parameters_timing_slow.csv --region global --basis consumption --samples 100000 --horizon 50 --out-dir results_final_v0.3.0/consumption/timing_slow_joint

# Solar-food-only timing runs (p_desal = 0)
ai-water-breakeven run --parameters results_final_v0.3.0/parameter_variants/parameters_timing_fast_sf_only.csv --region global --basis consumption --samples 100000 --horizon 50 --out-dir results_final_v0.3.0/consumption/timing_fast_sf_only
ai-water-breakeven run --parameters results_final_v0.3.0/parameter_variants/parameters_timing_central_sf_only.csv --region global --basis consumption --samples 100000 --horizon 50 --out-dir results_final_v0.3.0/consumption/timing_central_sf_only
ai-water-breakeven run --parameters results_final_v0.3.0/parameter_variants/parameters_timing_slow_sf_only.csv --region global --basis consumption --samples 100000 --horizon 50 --out-dir results_final_v0.3.0/consumption/timing_slow_sf_only
```

---

## 4. Analytical Semantics and Interpretation

1. **Unconditional Probability vs. Real-World Odds:**
   Monte Carlo break-even probabilities represent outcomes under sampled parameter distributions; they do not represent real-world forecast probabilities.
2. **Attribution Formulation:**
   Constant attribution share $\alpha_i$ is a modeling assumption, not an empirical observation. A technology acceleration framework is identified as future work.
3. **Threshold Reporting vs. Evaluation Horizon:**
   A run achieving cumulative balance $\ge 0$ by year 30 that subsequently turns negative before year 50 is not credited as sustained break-even through year 50.
4. **Dominance Safeguards:**
   Any input with $|PRCC| > 0.85$ triggers a `dominance_warning`. Realized deployment draws $s_*$ and break-even correlations $> 0.85$ trigger `breakeven_dominance_warning`.
