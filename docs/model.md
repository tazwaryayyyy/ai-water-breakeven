# Model Specification and Methodological Basis

## Accounting Framework

### Water Withdrawal vs. Water Consumption
Water accounting in this model maintains a strict separation between withdrawal and consumption:
- **Freshwater Withdrawal:** Total volume of freshwater extracted from surface or groundwater sources for operational cooling or industrial processing.
- **Freshwater Consumption:** The subset of withdrawn water evaporated, transpired, incorporated into products, or otherwise removed from the local hydrological basin.

Because the ratio of consumption to withdrawal varies substantially across cooling technologies (e.g., evaporative cooling towers consume 70–90% of withdrawn water, whereas once-through systems consume <5%), mixing withdrawal and consumption within a single scenario without an explicit hydrological conversion bridge represents a physical accounting error. Scenarios must evaluate either withdrawal or consumption across both costs and benefits.

### Operational Scopes
Data center water footprints encompass multiple operational tiers:
- **Scope 1 (Direct):** On-site water consumed or withdrawn for facility cooling, humidification, and facility operations.
- **Scope 2 (Indirect):** Off-site water consumed or withdrawn at power plants to generate the electricity supplied to compute infrastructure.
- **Scope 3 (Embodied):** Water used in upstream semiconductor fabrication, server manufacturing, and data center construction (currently excluded from this model).

In the global scenario configuration, baseline values from Li et al. (2025) combine Scope 1 and Scope 2 operational water into a single combined direct parameter (`W_direct_global`), setting `W_indirect_global = 0`. For US accounting, direct and indirect rows are separated using empirical benchmarks from LBNL-2001637, with the parameter $k \in [0, 1]$ acting as a toggle for indirect electricity water inclusion.

### Regional Scopes and Boundary Consistency
- **`region = "global"` (Runnable):** Evaluates combined global Scope 1+2 compute footprints against global desalination capacity and agricultural displacement potential.
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
For each potential benefit pathway $i \in \{\text{desal}, \text{solar\_food}\}$:

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
1. **Desalination Capacity & Efficiency Gains:**
   $$\text{Gross}_{\text{desal}} = D \cdot \theta$$
   where $D$ is baseline global desalination production volume (m³/yr), and $\theta$ is fractional efficiency/capacity enhancement enabled by AI process control.

2. **Electro-Agriculture / Solar Food Synthesis:**
   $$\text{Gross}_{\text{solar\_food}} = \phi \cdot A \cdot (1 - r)$$
   where $A$ is global agricultural freshwater footprint (m³/yr), $\phi$ is the fraction of conventional agriculture displaced by synthetic production, and $r$ is the relative water intensity of synthetic alternatives compared to conventional crops.

### Cumulative Balance and Break-Even Criteria
The cumulative net water balance from year 1 to year $t$ is:

$$N(t) = \sum_{\tau=1}^t \left( \sum_i B_i(\tau) - C(\tau) \right)$$

- **Sustained Break-Even Year ($t^*$):** The earliest year such that cumulative balance remains positive for all subsequent years through horizon $T$:
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

### Common-Random-Number (CRN) Knockouts
To isolate structural drivers without Monte Carlo sampling variance, knockout scenarios reuse identical pseudo-random draws from the baseline run while selectively overriding target parameter subsets:
- `alpha_1`: Attribution $\alpha_i = 1.0$ across all pathways.
- `success_1`: Success probability $p_i = 1.0$ across all pathways.
- `no_rebound`: Rebound factors $\rho_i = 0$.
- `no_delay`: Adoption lags $L_i = 0$ and ramps $R_i = 0$.
- `flat_cost`: Cost growth rates $g_1 = 0, g_2 = 0$.
- `desal_only`: Only desalination pathway active.
- `solar_food_only`: Only agricultural displacement pathway active.
- `ceiling`: Full deployment, 100% attribution, zero rebound, zero delay, flat cost.

### Break-Even Threshold Surface
A 2D threshold grid spans the 5th to 95th percentiles of two selected continuous parameters across $G \times G$ cells. For each cell, the break-even probability is computed over shared base draws of all remaining parameters, identifying critical non-linear feasibility boundaries.

---

## Reading Results

Results are stated as "in X% of simulated scenarios under these inputs", never as real-world probabilities; "never" means no sustained break-even within T.

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
9. **Sentinel Gross Benefits:** A basis_notice flags any pathway whose sampled gross benefit is identically zero (today the solar_food sentinels under basis=consumption).

---

## Parameter Catalog

| Parameter | Unit | Basis | Region | Dist | Low | Mode | High | Source | Conf | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `W_direct_global` | $\text{m}^3/\text{yr}$ | withdrawal | global | uniform | 4.2e9 | 5.4e9 | 6.6e9 | Li et al. (2025) | B | Combined Scope 1+2 global water withdrawal. |
| `W_indirect_global` | $\text{m}^3/\text{yr}$ | withdrawal | global | fixed | 0.0 | 0.0 | 0.0 | Li et al. (2025) | B | Zero by construction; Scope 2 is in direct row. |
| `W_direct_global_consumption` | $\text{m}^3/\text{yr}$ | consumption | global | uniform | 0.38e9 | 0.49e9 | 0.60e9 | Li et al. (2025) | B | Combined Scope 1+2 global water consumption. |
| `W_indirect_global_consumption` | $\text{m}^3/\text{yr}$ | consumption | global | fixed | 0.0 | 0.0 | 0.0 | Li et al. (2025) | B | Zero by construction; Scope 2 is in direct row. |
| `g_global` | dimensionless | n/a | global | triangular | 0.10 | 0.20 | 0.30 | IEA (2025) / LBNL / Xylem | C | Phase 1 growth rate; mode is judgment. No source covers 2035–2077. |
| `G_global` | yr | n/a | global | triangular | 1.0 | 3.0 | 8.0 | IEA (2025) / LBNL / Xylem | C | Phase 1 duration; mode is judgment. No source covers 2035–2077. |
| `g2_global` | dimensionless | n/a | global | triangular | -0.02 | 0.02 | 0.05 | IEA (2025) / LBNL / Xylem | C | Phase 2 growth rate; mode is judgment. No source covers 2035–2077. |
| `W_direct_us` | $\text{gal}/\text{yr}$ | consumption | us | triangular | 1.5e10 | 1.74e10 | 2.0e10 | LBNL (2024) | A | Direct on-site data center water consumption. |
| `W_indirect_us` | $\text{gal}/\text{yr}$ | consumption | us | triangular | 1.9e11 | 2.11e11 | 2.3e11 | LBNL (2024) | A | Indirect electricity-generation water consumption. |
| `g_us` | dimensionless | n/a | us | triangular | 0.15 | 0.20 | 0.32 | LBNL (2024) | B | Reserved: no runnable scenario uses US growth rows. |
| `G_us` | yr | n/a | us | triangular | 5.0 | 10.0 | 15.0 | PLACEHOLDER | C | Reserved: no runnable scenario uses US growth rows. |
| `g2_us` | dimensionless | n/a | us | triangular | -0.50 | 0.00 | 0.50 | PLACEHOLDER | C | Reserved: no runnable scenario uses US growth rows. |
| `p_desal` | dimensionless | n/a | global | uniform | 0.50 | 0.80 | 0.95 | PLACEHOLDER | C | Deployment probability for desalination efficiency. |
| `alpha_desal` | dimensionless | n/a | global | triangular | 0.05 | 0.15 | 0.30 | PLACEHOLDER | C | Counterfactual attribution share to AI. |
| `rho_desal` | dimensionless | n/a | global | triangular | 0.00 | 0.10 | 0.30 | PLACEHOLDER | C | Desalination rebound demand fraction. |
| `L_desal` | yr | n/a | global | triangular | 3.0 | 5.0 | 10.0 | PLACEHOLDER | C | Desalination deployment lag. |
| `R_desal` | yr | n/a | global | triangular | 5.0 | 10.0 | 20.0 | PLACEHOLDER | C | Desalination ramp-up duration. |
| `D_desal` | $\text{m}^3/\text{yr}$ | n/a | global | triangular | 2.5e10 | 3.5e10 | 4.5e10 | PLACEHOLDER | C | Global baseline desalination production volume. |
| `theta_desal` | dimensionless | n/a | global | triangular | 0.01 | 0.05 | 0.15 | PLACEHOLDER | C | Fractional capacity/efficiency gain. |
| `p_solar_food` | dimensionless | n/a | global | uniform | 0.10 | 0.30 | 0.60 | PLACEHOLDER | C | Deployment probability for electro-ag food synthesis. |
| `alpha_solar_food` | dimensionless | n/a | global | triangular | 0.10 | 0.25 | 0.50 | PLACEHOLDER | C | Counterfactual attribution share to AI. |
| `rho_solar_food` | dimensionless | n/a | global | triangular | 0.00 | 0.10 | 0.40 | PLACEHOLDER | C | Solar food rebound demand fraction. |
| `L_solar_food` | yr | n/a | global | triangular | 5.0 | 10.0 | 15.0 | PLACEHOLDER | C | Solar food deployment lag. |
| `R_solar_food` | yr | n/a | global | triangular | 5.0 | 10.0 | 20.0 | PLACEHOLDER | C | Solar food ramp-up duration. |
| `phi_solar_food` | dimensionless | n/a | global | triangular | 0 | 0.06 | 0.13 | Pikaar et al. (2018) | C | Assumption; covers all microbial-protein routes, not only solar-driven ones; cropland share is a proxy for blue-water share and displaced crops are largely rain-fed, so this is likely generous. |
| `A_solar_food` | $\text{m}^3/\text{yr}$ | withdrawal | global | triangular | 2.0e12 | 2.8e12 | 3.5e12 | MISSING | C | Baseline agricultural freshwater withdrawal. |
| `r_solar_food` | dimensionless | withdrawal | global | triangular | 0.05 | 0.20 | 0.50 | MISSING | C | Relative water intensity (withdrawal basis). |
| `A_solar_food_consumption` | $\text{m}^3/\text{yr}$ | consumption | global | triangular | 0.89e12 | 1.08e12 | 1.23e12 | Chukalla et al. (2025) / Mekonnen & Hoekstra (2011) | B | Crop production only; held constant over the horizon; read from secondary summaries, check against the papers. |
| `r_solar_food_consumption` | dimensionless | consumption | global | triangular | 0.002 | 0.01 | 0.10 | Sillman et al. (2020) | C | Assumption informed by best-case life-cycle blue water of 1-3.8 kg per kg protein against a corrected soybean comparator of 630 L per kg protein; the corrected table was not checked; the mode is a judgment and the upper bound is deliberately generous. |
