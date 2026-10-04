# Model Specification and Methodological Basis

## Definitions

### Water Withdrawal and Water Consumption
- **Water Withdrawal**: Water withdrawal is defined as the total volume of freshwater extracted from surface or groundwater sources for operational use.
- **Water Consumption**: Water consumption is defined as the portion of withdrawn water evaporated, transpired, incorporated into products, or otherwise removed from the immediate aquatic ecosystem.
- **Cross-Basis Separation**: Mixing withdrawal metrics and consumption metrics within a single scenario without an explicit hydrological accounting bridge constitutes a physical category error.

### Scenario Dimensions: Region and Physical Basis
- **Region Dimension**: The model accepts `global` or `us` as independent scenario regions.
- **Physical Basis Dimension**: The model accepts `withdrawal` or `consumption` as independent physical bases.
- **Parameter Selection Rule**: A simulation run selects only parameters matching its designated region and physical basis, alongside parameters marked `n/a`.
- **Regional Consistency Rule**: A run configured with a `us` cost set cannot be paired with `global` benefit rows and requires explicit US benefit parameters.

### Operational Scopes and Global Cost Definition
- **Scope 1 Water Use**: Scope 1 operational water is defined as on-site data center cooling and facility consumption.
- **Scope 2 Water Use**: Scope 2 operational water is defined as off-site water consumed or withdrawn in generating purchased electricity for compute facilities.
- **Global Scope Formulation**: Global AI cost parameters are defined as Scope 1 and Scope 2 combined, derived from Li et al. (2025).
- **Indirect Global Component**: The parameter `W_indirect_global` is defined as zero by construction because Scope 2 electricity water is already incorporated in `W_direct_global`.
- **Scope Switch ($k$)**: The switch parameter $k \in [0, 1]$ represents the fraction of indirect electricity water included and applies only to US scenarios where direct and indirect rows are separately reported.

### Sensitivity and Evaluation Concepts
- **Partial Rank Correlation Coefficient (PRCC)**: PRCC is defined as a partial correlation between the rank-transformed input parameter and the rank-transformed final net balance $N(T)$, controlling for linear effects among ranks of all other sampled parameters.
- **PRCC Non-Equivalence to Variance Explained**: PRCC is a rank association metric and is not a measure of variance explained ($R^2$).
- **Provisional Rank Status**: PRCC rankings depend directly on specified input intervals and distributions and remain provisional while inputs are marked `PLACEHOLDER` or `MISSING`.
- **Common-Random-Number Knockouts**: Knockout analysis is defined as the deterministic override of specific parameter subsets across identical Latin-hypercube Monte Carlo draws to isolate structural drivers without sampling variance.
- **Break-Even Threshold Map**: A threshold map is defined as a two-dimensional grid spanning the 5th to 95th percentiles of two chosen parameters, where sustained break-even probability is computed per cell over shared base draws of all remaining parameters.

---

## Governing Equations

### Two-Phase Cost Growth
The annual operational water requirement of AI at year $t \in [1, T]$ is governed by:

$$C(t) = (W_{\text{direct}} + k \cdot W_{\text{indirect}}) \cdot (1 + g_1)^{\min(t, G_1)} \cdot (1 + g_2)^{\max(t - G_1, 0)}$$

where:
- $W_{\text{direct}}$ is baseline direct annual water volume ($\text{m}^3/\text{yr}$ or $\text{gal}/\text{yr}$ converted to $\text{m}^3/\text{yr}$).
- $W_{\text{indirect}}$ is baseline indirect annual electricity water volume ($\text{m}^3/\text{yr}$ or $\text{gal}/\text{yr}$ converted to $\text{m}^3/\text{yr}$).
- $k \in [0, 1]$ is the indirect electricity water accounting switch.
- $g_1 > -1$ is the first-phase annual growth rate.
- $G_1 \ge 0$ is the duration of the first growth phase in years.
- $g_2 > -1$ is the second-phase annual growth rate, representing post-transition expansion or technological efficiency gains.

### Technology Deployment and Ramp
For each benefit pathway $i$:

$$s_i \sim \text{Bernoulli}(p_i)$$

$$\text{ramp}_i(t) = \begin{cases} 1[t > L_i] & \text{if } R_i = 0 \\ \operatorname{clip}\left(\frac{t - L_i}{R_i}, 0, 1\right) & \text{if } R_i > 0 \end{cases}$$

where $p_i \in [0, 1]$ is deployment probability, $L_i \ge 0$ is adoption lag in years, and $R_i \ge 0$ is ramp-up duration in years.

### Net Pathway Benefit
The annual net attributable benefit of pathway $i$ at year $t$ is:

$$B_i(t) = s_i \cdot \alpha_i \cdot \text{Gross}_i \cdot \text{ramp}_i(t) \cdot (1 - \rho_i)$$

where $\alpha_i \in [0, 1]$ is the AI attribution share, and $\rho_i \ge 0$ is the rebound effect fraction.

### Pathway Gross Formulations
1. **Solar Food / Electro-Agriculture**:
   $$\text{Gross}_{\text{solar\_food}} = \phi \cdot A \cdot (1 - r)$$
   where $\phi \in [0, 1]$ is the agricultural displacement fraction, $A \ge 0$ is global baseline agricultural blue-water volume, and $r \in [0, 1]$ is the relative water intensity of synthesized food.
2. **Desalination Expansion**:
   $$\text{Gross}_{\text{desal}} = D \cdot \theta$$
   where $D \ge 0$ is baseline global desalination output volume, and $\theta \in [0, 1]$ is the fractional efficiency and capacity increase attributable to AI.

### Cumulative Balance and Break-Even Metrics
The cumulative net water balance from year 1 to year $t$ is:

$$N(t) = \sum_{\tau=1}^t \left( \sum_i B_i(\tau) - C(\tau) \right)$$

- **Sustained Break-Even Year ($t^*$)**: The minimum year $t^* \in [1, T]$ such that $N(\tau) \ge 0$ for all $\tau \in [t^*, T]$.
- **Annual Crossover Year**: The earliest year $t \in [1, T]$ where annual benefits equal or exceed annual costs: $\sum_i B_i(t) \ge C(t)$.
- **Horizon Net Balance**: The cumulative water balance evaluated at the final simulation horizon: $N(T)$.

---

## Assumptions

1. **Parameter Sampling Independence**: All sampled parameters are assumed to follow independent marginal distributions without copulas or correlation matrices.
2. **Attribution Invariance**: AI attribution share $\alpha_i$ is assumed constant over time for each pathway.
3. **Constant Baseline Resource Demands**: Global agricultural blue-water volume $A$ and desalination production $D$ are assumed constant across the simulation horizon.
4. **Agricultural Water Scope**: Baseline agricultural volume $A$ is assumed to represent irrigation (blue) water on the specified physical basis.
5. **Desalination Supply Accounting**: Desalination is assumed to provide new water supply rather than demand reduction, acting as a volumetric supply credit under consumption accounting.
6. **Two-Phase Regime Shift**: Data center water use is assumed to experience compound growth at rate $g_1$ for $G_1$ years, shifting abruptly to compound rate $g_2$ thereafter.
7. **Knockout Invariance**: Common-random-number knockout scenarios assume that individual parameter overrides do not alter the realized marginal draws of non-overridden parameters.

---

## Reading Results

- All outputs are conditional scenario outcomes under exploratory input distributions.
- Statements describing model outputs must be phrased strictly as "in $X\%$ of simulated scenarios under these inputs", never as empirical forecasts or real-world probabilities.
- A break-even probability of zero denotes that zero sampled parameter combinations achieved break-even within the evaluation horizon under current inputs.

---

## Limitations

1. **Aggregate Spatial Scale**: Volumetric balances are computed at global or national scale and do not represent watershed-level hydrological balances.
2. **Absence of Scarcity Weighting**: The model does not weigh water savings by local water stress indices or aquifer depletion rates.
3. **Exclusion of Embodied Water**: Scope 3 embodied water consumed during semiconductor manufacturing, server fabrication, and facility construction is excluded.
4. **Static Macroeconomic Baselines**: Baseline water volumes $A$ and $D$ do not incorporate dynamic climate change, demographic shifts, or dietary transitions.
5. **Absence of Economic Discounting**: Water balances are evaluated in physical volumetric units ($\text{m}^3$) without financial discounting or capital cost trade-offs.
6. **Long-Horizon Coverage**: No source covers 2035-2077, which is most of the horizon; growth assumptions across this window reflect scenario assumptions rather than empirical projections.

---

## Parameter Catalog

| Parameter | Unit | Basis | Region | Dist | Low | Mode | High | Source | Conf | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `W_direct_global` | $\text{m}^3/\text{yr}$ | withdrawal | global | uniform | 4.2e9 | 5.4e9 | 6.6e9 | Li, Yang, Islam and Ren (2025) | B | Combined Scope 1+2 global water withdrawal. |
| `W_indirect_global` | $\text{m}^3/\text{yr}$ | withdrawal | global | fixed | 0.0 | 0.0 | 0.0 | Li, Yang, Islam and Ren (2025) | B | Zero by construction; Scope 2 is in direct row. |
| `W_direct_global_consumption` | $\text{m}^3/\text{yr}$ | consumption | global | uniform | 0.38e9 | 0.49e9 | 0.60e9 | Li, Yang, Islam and Ren (2025) | B | Combined Scope 1+2 global water consumption. |
| `W_indirect_global_consumption` | $\text{m}^3/\text{yr}$ | consumption | global | fixed | 0.0 | 0.0 | 0.0 | Li, Yang, Islam and Ren (2025) | B | Zero by construction; Scope 2 is in direct row. |
| `g_global` | dimensionless | n/a | global | triangular | 0.10 | 0.20 | 0.30 | IEA (2025) / LBNL / Xylem | C | First-phase rate; mode is judgment. No source covers 2035-2077. |
| `G_global` | yr | n/a | global | triangular | 1.0 | 3.0 | 8.0 | IEA (2025) / LBNL / Xylem | C | First-phase duration; mode is judgment. No source covers 2035-2077. |
| `g2_global` | dimensionless | n/a | global | triangular | -0.02 | 0.02 | 0.05 | IEA (2025) / LBNL / Xylem | C | Second-phase rate; mode is judgment. No source covers 2035-2077. |
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
| `phi_solar_food` | dimensionless | n/a | global | triangular | 0.005 | 0.02 | 0.08 | PLACEHOLDER | C | Fractional agricultural displacement share. |
| `A_solar_food` | $\text{m}^3/\text{yr}$ | withdrawal | global | triangular | 2.0e12 | 2.8e12 | 3.5e12 | MISSING | C | Baseline agricultural freshwater withdrawal. |
| `r_solar_food` | dimensionless | withdrawal | global | triangular | 0.05 | 0.20 | 0.50 | MISSING | C | Relative water intensity (withdrawal basis). |
| `A_solar_food_consumption` | $\text{m}^3/\text{yr}$ | consumption | global | fixed | 0.0 | 0.0 | 0.0 | PLACEHOLDER | C | Sentinel agricultural consumption volume. |
| `r_solar_food_consumption` | dimensionless | consumption | global | fixed | 1.0 | 1.0 | 1.0 | PLACEHOLDER | C | Sentinel relative water intensity (consumption). |
