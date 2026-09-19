# Model Specification and Methodological Basis

## Definitions

### Withdrawal versus Consumption
- **Water Withdrawal**: The total volume of freshwater abstracted from surface or groundwater sources for human use. Substantial portions of withdrawn water are frequently returned to the original watershed as return flows, albeit often with degraded quality or altered thermal profiles.
- **Water Consumption**: The portion of withdrawn water permanently removed from the immediate aquatic ecosystem through evaporation, transpiration, incorporation into manufactured goods or agricultural biomass, or transfer to another basin.
- **Cross-Basis Comparison**: Withdrawing one cubic meter of water is physically and ecologically distinct from consuming one cubic meter. Consequently, mixing cost and benefit metrics across different physical bases without an explicit accounting bridge yields spurious balances. The model enforces basis consistency by default.

### Direct versus Indirect Water Use
- **Direct Water Use ($W_{\text{direct}}$)**: On-site water consumed or withdrawn for cooling data center compute facilities (e.g., evaporative cooling towers, direct-to-chip closed-loop cooling replenishment).
- **Indirect Water Use ($W_{\text{indirect}}$)**: Off-site water consumed or withdrawn in generating the thermal and hydroelectric power that supplies electricity to the compute facilities.
- **Switch Parameter ($k$)**: A scenario switch where $k = 0$ isolates direct facility water use, and $k = 1$ accounts for full scope (direct plus electricity generation indirect water use).

---

## Governing Equations

### Cost Trajectory
The operational water use of AI at year $t \in [1, T]$ is governed by:

$$C(t) = (W_{\text{direct}} + k \cdot W_{\text{indirect}}) \cdot (1 + g)^{\min(t, G)}$$

where:
- $W_{\text{direct}}$ and $W_{\text{indirect}}$ are baseline annual volumes ($\text{m}^3/\text{yr}$).
- $g$ is the net annual growth rate of compute water demand.
- $G$ is the duration in years over which demand compounds before reaching a plateau.

### Benefit Pathways
For each pathway $i$ (e.g., desalination efficiency, solar food displacement):

1. **Technology Deployment**:
   $$s_i \sim \text{Bernoulli}(p_i)$$
   where $p_i$ is the probability that the technology reaches commercial deployment.

2. **Temporal Adoption Ramp**:
   $$\text{ramp}_i(t) = \begin{cases} 1[t > L_i] & \text{if } R_i = 0 \\ \operatorname{clip}\left(\frac{t - L_i}{R_i}, 0, 1\right) & \text{if } R_i > 0 \end{cases}$$
   where $L_i$ is the adoption lag in years and $R_i$ is the ramp-up duration in years.

3. **Net Attributable Benefit**:
   $$B_i(t) = s_i \cdot \alpha_i \cdot \text{Gross}_i \cdot \text{ramp}_i(t) \cdot (1 - \rho_i)$$
   where $\alpha_i \in [0, 1]$ is the counterfactual attribution share assignable to AI, and $\rho_i \ge 0$ is the rebound effect fraction.

4. **Pathway Gross Formulations**:
   - **Solar Food / Electro-Agriculture**:
     $$\text{Gross}_{\text{solar\_food}} = \phi \cdot A \cdot (1 - r)$$
     $\phi$ is the share of conventional agricultural production displaced, $A$ is global agricultural water withdrawal, and $r$ is the relative water intensity of synthesized food compared to conventional farming.
   - **Desalination Supply Expansion**:
     $$\text{Gross}_{\text{desal}} = D \cdot \theta$$
     $D$ is global desalinated water output, and $\theta$ is the fractional increase in supply attributable to AI optimization and energy-reduction advances. **Important Note**: Desalination adds water supply to coastal regions; it does not reduce existing freshwater demand or consumption.

### Cumulative Balance and Metrics
The cumulative net water balance from year 1 to year $t$ is:

$$N(t) = \sum_{\tau=1}^t \left( \sum_i B_i(\tau) - C(\tau) \right)$$

- **Primary Metric (Sustained Break-Even Year)**: The earliest year $t^* \in [1, T]$ such that $N(\tau) \ge 0$ for every $\tau \in [t^*, T]$. If $N(\tau) < 0$ for any $\tau \ge t^*$, or if $N(T) < 0$, the outcome is recorded as right-censored ("never within T").
- **Secondary Metric (Annual Crossover Year)**: The first year $t$ where annual benefits meet or exceed annual cost: $\sum_i B_i(t) \ge C(t)$.
- **Secondary Metric (Horizon Net Balance)**: Cumulative net balance at horizon $N(T)$.

---

## Parameter Catalog

| Parameter | Unit | Basis | Dist | Low | Mode | High | Source | Conf |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `W_direct_global` | $\text{m}^3/\text{yr}$ | withdrawal | uniform | 4.2e9 | 5.4e9 | 6.6e9 | Ren et al., "Making AI Less Thirsty" | B |
| `W_indirect_global`| $\text{m}^3/\text{yr}$ | withdrawal | fixed | 0.0 | 0.0 | 0.0 | PLACEHOLDER | C |
| `g_global` | dimensionless | n/a | triangular | 0.05 | 0.15 | 0.25 | PLACEHOLDER | C |
| `G_global` | yr | n/a | triangular | 5.0 | 10.0 | 15.0 | PLACEHOLDER | C |
| `W_direct_us` | $\text{gal}/\text{yr}$ | consumption | triangular | 1.5e10 | 1.74e10 | 2.0e10 | LBNL-2001637 (2024 Report) | A |
| `W_indirect_us` | $\text{gal}/\text{yr}$ | consumption | triangular | 1.9e11 | 2.11e11 | 2.3e11 | LBNL-2001637 (2024 Report) | A |
| `g_us` | dimensionless | n/a | triangular | 0.15 | 0.20 | 0.32 | LBNL-2001637 (2024 Report) | B |
| `G_us` | yr | n/a | triangular | 5.0 | 10.0 | 15.0 | PLACEHOLDER | C |
| `p_desal` | dimensionless | n/a | uniform | 0.50 | 0.80 | 0.95 | PLACEHOLDER | C |
| `alpha_desal` | dimensionless | n/a | triangular | 0.05 | 0.15 | 0.30 | PLACEHOLDER | C |
| `rho_desal` | dimensionless | n/a | triangular | 0.00 | 0.10 | 0.30 | PLACEHOLDER | C |
| `L_desal` | yr | n/a | triangular | 3.0 | 5.0 | 10.0 | PLACEHOLDER | C |
| `R_desal` | yr | n/a | triangular | 5.0 | 10.0 | 20.0 | PLACEHOLDER | C |
| `D_desal` | $\text{m}^3/\text{yr}$ | withdrawal | triangular | 2.5e10 | 3.5e10 | 4.5e10 | PLACEHOLDER | C |
| `theta_desal` | dimensionless | n/a | triangular | 0.01 | 0.05 | 0.15 | PLACEHOLDER (Context: Elimelech 2011) | C |
| `p_solar_food` | dimensionless | n/a | uniform | 0.10 | 0.30 | 0.60 | PLACEHOLDER | C |
| `alpha_solar_food` | dimensionless | n/a | triangular | 0.10 | 0.25 | 0.50 | PLACEHOLDER | C |
| `rho_solar_food` | dimensionless | n/a | triangular | 0.00 | 0.10 | 0.40 | PLACEHOLDER | C |
| `L_solar_food` | yr | n/a | triangular | 5.0 | 10.0 | 15.0 | PLACEHOLDER | C |
| `R_solar_food` | yr | n/a | triangular | 5.0 | 10.0 | 20.0 | PLACEHOLDER | C |
| `phi_solar_food` | dimensionless | n/a | triangular | 0.005 | 0.02 | 0.08 | PLACEHOLDER | C |
| `A_solar_food` | $\text{m}^3/\text{yr}$ | withdrawal | triangular | 2.0e12 | 2.8e12 | 3.5e12 | MISSING (FAO AQUASTAT ~70% share) | C |
| `r_solar_food` | dimensionless | n/a | triangular | 0.05 | 0.20 | 0.50 | MISSING (Joule 2024 energy only) | C |

---

## Key Assumptions

1. **Independent Sampling**: All parameter distributions are sampled independently via Latin Hypercube Sampling. No latent correlation structure is assumed between economic growth, AI computational efficiency, and technological adoption.
2. **Attribution Linearity**: Counterfactual attribution $\alpha$ is assumed constant across the operational life of each technology.
3. **Compound Ceilings**: Exponential growth compounds for a finite duration $G$ before plateauing, reflecting physical, electrical, and supply chain bottlenecks.

---

## What This Model Cannot Tell You

1. **Local Hydrological Stress**: Global volumetric aggregation masks localized hydrological realities. One cubic meter of water conserved in a water-abundant basin (e.g., the Pacific Northwest) does not mitigate, recharge, or offset one cubic meter evaporated in a severely stressed aquifer (e.g., the Ogallala or Phoenix active management areas).
2. **Economic Discounting**: The model evaluates purely physical volumetric balances across time with zero discount rate. It does not calculate present economic values or opportunity costs of capital invested in compute infrastructure versus water conservation infrastructure.
3. **Attribution Is an Analytical Choice**: The attribution parameter $\alpha$ is a modeled counterfactual assumption, not an empirical physical constant. Determining how much of a biological or industrial process breakthrough is attributable specifically to AI versus broader mechanical, civil, or chemical engineering cannot be directly measured.
4. **Parameter Independence in Reality**: In reality, high energy prices or climate stress might simultaneously accelerate desalination adoption while constraining data center expansion. These macroeconomic feedbacks are outside the model's structural scope.
