# Model Specification and Methodological Basis

## Accounting Framework

### Water Withdrawal vs. Water Consumption
Water accounting in this model maintains a strict separation between withdrawal and consumption:
- **Freshwater Withdrawal:** Total volume of freshwater extracted from surface or groundwater sources for operational cooling or industrial processing.
- **Freshwater Consumption:** The subset of withdrawn water evaporated, transpired, incorporated into products, or otherwise removed from the local hydrological basin.

Because the ratio of consumption to withdrawal varies substantially across cooling technologies, mixing withdrawal and consumption within a single scenario without an explicit hydrological conversion bridge represents a physical accounting error. Scenarios must evaluate either withdrawal or consumption across both costs and benefits.

### Operational Scopes
Data center water footprints encompass multiple operational tiers:
- **Scope 1 (Direct):** On-site water consumed or withdrawn for facility cooling, humidification, and facility operations.
- **Scope 2 (Indirect):** Off-site water consumed or withdrawn at power plants to generate the electricity supplied to compute infrastructure.
- **Scope 3 (Embodied):** Water used in upstream semiconductor fabrication, server manufacturing, and data center construction (currently excluded from this model).

In the global scenario configuration, baseline values from Li et al. (2025) combine Scope 1 and Scope 2 operational water into a single combined direct parameter (`W_direct_global`), setting `W_indirect_global = 0`. For US accounting, direct and indirect rows are separated using empirical benchmarks from LBNL-2001637 (Shehabi et al. 2024, doi:10.71468/P1WC7Q), with the parameter $k \in [0, 1]$ acting as a toggle for indirect electricity water inclusion.

### Regional Scopes and Boundary Consistency
- **`region = "global"` (Runnable):** Evaluates combined global Scope 1+2 compute footprints against global desalinated output and agricultural displacement potential.
- **`region = "us"` (Reserved / Non-runnable):** US data center water parameters are recorded in `data/parameters.csv` for reference (17.4 billion gallons direct, 211 billion gallons indirect electricity consumption for 2023, based on LBNL-2001637). However, benefit pathways are not parameterized at the US scale. Pairing US costs with global benefits produces an invalid comparison and is blocked during parameter validation.

---

## Governing Equations

### Two-Phase Operational Cost Trajectory
Annual operational water demand $C(t)$ across years $t \in [1, T]$ is governed by a two-phase compounding growth function:

$$C(t) = (W_{\text{direct}} + k \cdot W_{\text{indirect}}) \cdot (1 + g_1)^{\min(t, G_1)} \cdot (1 + g_2)^{\max(t - G_1, 0)}$$

where:
- $W_{\text{direct}}$: Baseline direct annual water volume (m³/yr).
- $W_{\text{indirect}}$: Baseline indirect annual electricity water volume (m³/yr).
- $k \in [0, 1]$: Indirect electricity water switch (active only when direct and indirect are separated).
- $g_1$: Phase 1 annual compound growth rate (informed by near-term AI infrastructure expansion).
- $G_1$: Duration of Phase 1 in years.
- $g_2$: Phase 2 long-term annual growth rate (reflecting saturation or post-transition efficiency gains).

### Technology Deployment and Ramp
For each potential benefit pathway $i \in \{\text{desal}, \text{solar food}\}$:

$$s_i \sim \text{Bernoulli}(p_i)$$

$$\text{ramp}_i(t) = \begin{cases} 1[t > L_i] & \text{if } R_i = 0 \\ \operatorname{clip}\left(\frac{t - L_i}{R_i}, 0, 1\right) & \text{if } R_i > 0 \end{cases}$$

where $p_i$ is deployment probability, $L_i$ is adoption lag in years, and $R_i$ is ramp-up duration in years.

### Net Pathway Benefit
The net annual water savings credited to AI from pathway $i$ at year $t$ is:

$$B_i(t) = s_i \cdot \alpha_i \cdot \text{Gross}_i \cdot \text{ramp}_i(t) \cdot (1 - \rho_i)$$

where:
- $\alpha_i \in [0, 1]$: Fractional attribution share credited to AI innovations.
- $\rho_i \ge 0$: Rebound effect factor (additional water consumption induced by lower technology costs or efficiency gains).

### Gross Pathway Potentials
1. **Desalination Output & Efficiency Gains:**
   $$\text{Gross}_{\text{desal}} = D \cdot \theta$$
   where $D$ is global desalinated output (m³/yr) and $\theta$ is the fractional increase in that output from cost and energy improvements, from all causes. The AI share of the benefit is applied separately through $\alpha$. Desalination adds supply; it does not reduce consumption.

2. **Electro-Agriculture / Solar Food Synthesis:**
   $$\text{Gross}_{\text{solar food}} = \phi \cdot A \cdot (1 - r)$$
   where $A$ is baseline agricultural water use on the chosen basis (crop blue-water consumption, or irrigation withdrawal), $\phi$ is the share of $A$ displaced, and $r$ is the water intensity of the solar-driven food system relative to conventional production (0 = none, 1 = equal).

### Cumulative Balance and Break-Even Criteria
The cumulative net water balance from year 1 to year $t$ is:

$$N(t) = \sum_{\tau=1}^t \left( \sum_i B_i(\tau) - C(\tau) \right)$$

- **Sustained Break-Even Year ($t^*$):** The earliest year such that cumulative balance stays non-negative for all subsequent years through horizon $T$:
  $$t^* = \min \{ t \in [1, T] : N(\tau) \ge 0 \quad \forall \tau \in [t, T] \}$$
- **Annual Crossover Year:** The earliest individual year where annual benefit meets or exceeds annual cost:
  $$t_{\text{cross}} = \min \left\{ t \in [1, T] : \sum_i B_i(t) \ge C(t) \right\}$$
- **Horizon Net Balance ($N(T)$):** Cumulative freshwater surplus or deficit at the terminal simulation year $T$.

---

## Sensitivity and Scenario Methods

### Latin Hypercube Sampling (LHS)
Parameters with defined uncertainty ranges are sampled via Latin Hypercube Sampling across specified distributions (uniform, triangular, or fixed). Marginal distributions are sampled independently.

### Partial Rank Correlation Coefficients (PRCC)
Sensitivity rankings evaluate monotonic non-linear relationships between sampled input parameters and cumulative balance $N(T)$ using PRCC:
- PRCC measures the correlation between rank-transformed inputs and rank-transformed outputs after partialling out rank correlations with all other inputs.
- PRCC is an index of monotonic sensitivity, not a decomposition of variance explained ($R^2$).
- **Dominance Safeguard:** If any parameter exhibits $|PRCC| > 0.85$, it is flagged with a `dominance_warning` in `sourcing_priority.csv` and triggers a console warning during simulation execution.

The `sourcing_priority.csv` table includes two sensitivity columns and one deployment row per pathway:
- `abs_corr_breakeven`: Absolute partial rank correlation of each sampled continuous parameter and realized deployment draw against the sustained break-even year, with "never" coded as $T+1$.
- `abs_prcc`: Absolute partial rank correlation of each sampled continuous parameter against the cumulative net balance $N(T)$.
- `s_<pathway>` rows: Realized Bernoulli deployment draws whose break-even correlations are reported in `abs_corr_breakeven`, with `prcc` and `abs_prcc` left empty because the dominance check applies only to continuous parameters.

### Common-Random-Number (CRN) Knockouts
To isolate structural drivers without Monte Carlo sampling variance, knockout scenarios reuse identical pseudo-random draws from the baseline run while selectively overriding target parameter subsets:
- `alpha_1`: Attribution $\alpha_i = 1.0$ across all pathways.
- `success_1`: Success probability $p_i = 1.0$ across all pathways.
- `no_rebound`: Rebound factors $\rho_i = 0$.
- `no_delay`: Adoption lags $L_i = 0$ and ramps $R_i = 0$.
- `flat_cost`: Cost growth rates $g_1 = 0, g_2 = 0$.
- `desal_only`: Only the desalination pathway can deploy (`p_solar_food = 0`).
- `solar_food_only`: Only the solar-food pathway can deploy (`p_desal = 0`).
- `ceiling`: Attribution $\alpha_i = 1.0$, all deployment probabilities $p_i = 1.0$ with realized deployments forced to 1, rebound $\rho_i = 0$; lags, ramps and cost growth unchanged.

### Break-Even Threshold Surface
A 2D threshold grid spans the 5th to 95th percentiles of two selected continuous parameters across $G \times G$ cells. For each cell, the break-even probability is computed over shared base draws of all remaining parameters, showing where the break-even probability changes.

Threshold analysis supports optional range overrides (`--x-range LO HI`, `--y-range LO HI`) and log-spacing (`--log`) for grids spanning multiple orders of magnitude. Axis labels and the x and y columns of `threshold_map.csv` reflect the range actually used.

---

## Reading Results

Results are stated as "in X% of simulated scenarios under these inputs", never as real-world probabilities; "never" means no sustained break-even within $T$.

Deployment is a single Bernoulli draw per pathway, so the break-even probability is bounded above by the probability that at least one pathway deploys; report the `success_1` knockout and the threshold map alongside it.

`conditional.csv` reports, for solar_food, desal and any, the runs in which that pathway (or either) deploys: the deployment probability, the share of those runs with sustained break-even by each horizon (Wilson 95% intervals), the share that never break even within $T$, and the median and 5th to 95th percentile break-even year among those that do.

---

## Boundary Conditions and Methodological Limitations

1. **Spatial Aggregation:** Volumetric balances are calculated at global scale. Water is physically non-fungible across regional watersheds; savings in an agricultural basin cannot offset cooling extraction from a stressed urban aquifer thousands of miles away.
2. **Absence of Scarcity Weighting:** Cubic meters are aggregated without weighting by watershed-level baseline water stress, groundwater depletion rates, or seasonal flow variability.
3. **Exclusion of Embodied Water (Scope 3):** Upstream water consumption in semiconductor supply chains (wafer fabrication, chemical refining) and facility construction is omitted.
4. **Long-Horizon Projection Gaps:** Empirical data center power and water projections extend through 2030–2035 (IEA, LBNL). Growth assumptions between 2035 and 2077 reflect scenario assumptions rather than empirical forecasts.
5. **Static Macroeconomic Baselines:** Desalination baseline $D$ and agricultural baseline $A$ are held constant over time, without dynamic feedback from climate change, population growth, or dietary shifts.
6. **Interpretive Boundary:** All outputs reflect conditional outcomes under exploratory input distributions. They do not constitute deterministic forecasts of real-world water balances.
7. **No Discounting:** No discounting is applied.
8. **Independent Sampling:** Inputs are sampled independently.
9. **Sentinel Gross Benefits:** A `basis_notice` flags any pathway whose sampled gross benefit is identically zero; with the current inputs none is.
10. **AI-System Footprint:** The water footprint of the AI-enabled systems themselves (sensors, inference) is not modeled beyond the pathway intensity $r$.

---

## Parameters

The parameter catalog is `data/parameters.csv`. Each row gives unit, basis, region, distribution (low, mode, high), source, locator, confidence and notes. Confidence A: point value reported by the cited primary source (any spread is the author's). Confidence B: range published by, or arithmetically derived from, the cited source; the distribution shape is the author's. Confidence C: assumption informed by sources; the mode is a judgment. Rows whose source is PLACEHOLDER or MISSING are unverified.
