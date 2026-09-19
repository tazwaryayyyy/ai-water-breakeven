"""Latin Hypercube sampling and inverse cumulative distribution transforms."""

from typing import Dict, List, Tuple

import numpy as np
from scipy.stats import lognorm, qmc, triang

from ai_water_breakeven.params import Parameter

Z_95: float = 1.6448536269514722


def sample_inverse_cdf(param: Parameter, u: np.ndarray) -> np.ndarray:
    """Transform standard uniform quantiles into parameter samples via inverse CDF."""
    dist, low, mode, high = param.distribution, param.low, param.mode, param.high
    if dist == "fixed" or high == low:
        return np.full_like(u, mode)
    if dist == "uniform":
        return low + u * (high - low)
    if dist == "triangular":
        c = np.clip((mode - low) / (high - low), 1e-9, 1.0 - 1e-9)
        return triang.ppf(u, c=c, loc=low, scale=high - low)
    if dist == "lognormal":
        sigma = (np.log(high) - np.log(low)) / (2.0 * Z_95)
        mu = (np.log(high) + np.log(low)) / 2.0
        return lognorm.ppf(u, s=sigma, scale=np.exp(mu))
    raise ValueError(f"Unsupported distribution '{dist}'")


def create_scenario_rng(master_seed: int, scenario_idx: int) -> np.random.Generator:
    """Spawn independent random number streams using SeedSequence."""
    return np.random.default_rng(
        np.random.SeedSequence(master_seed).spawn(scenario_idx + 1)[scenario_idx]
    )


def sample_parameter_matrix(
    params: List[Parameter], n: int, rng: np.random.Generator
) -> Tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    """Draw Latin Hypercube samples independently across all specified continuous parameters."""
    sampler = qmc.LatinHypercube(d=len(params) + 2, seed=rng)
    u_mat = sampler.random(n=n)
    sampled = {p.name: sample_inverse_cdf(p, u_mat[:, i]) for i, p in enumerate(params)}
    # Bernoulli technology draws s_i ~ Bernoulli(p_i)
    k_des = (u_mat[:, len(params)] < sampled.get("p_desal", np.ones(n))).astype(float)
    k_food = (u_mat[:, len(params) + 1] < sampled.get("p_solar_food", np.ones(n))).astype(float)
    return sampled, {"s_desal": k_des, "s_solar_food": k_food}
