"""Vectorized Monte Carlo simulation, sensitivity analysis, and convergence checking."""

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import binomtest, rankdata

from ai_water_breakeven.model import (
    calc_benefit_desal,
    calc_benefit_solar_food,
    calc_cost,
    calc_net_balance,
    find_annual_crossover,
    find_sustained_breakeven,
)
from ai_water_breakeven.params import Parameter
from ai_water_breakeven.sample import create_scenario_rng, sample_parameter_matrix

BENEFIT_KEYS = [
    "p_desal",
    "alpha_desal",
    "rho_desal",
    "L_desal",
    "R_desal",
    "D_desal",
    "theta_desal",
    "p_solar_food",
    "alpha_solar_food",
    "rho_solar_food",
    "L_solar_food",
    "R_solar_food",
    "phi_solar_food",
    "A_solar_food",
    "r_solar_food",
]


def _get_active_keys(pfx: str) -> List[str]:
    return [f"W_direct_{pfx}", f"W_indirect_{pfx}", f"g_{pfx}", f"G_{pfx}"] + BENEFIT_KEYS


@dataclass
class SimulationResults:
    t_horizon: int
    n_samples: int
    cost_basis: str
    cost_scope: str
    k_switch: float
    time_steps: np.ndarray
    net_balance_trajectories: np.ndarray
    be_years: np.ndarray
    crossover_years: np.ndarray
    final_net_balances: np.ndarray
    desal_benefits: np.ndarray
    solar_food_benefits: np.ndarray
    sampled_params: Dict[str, np.ndarray]
    has_placeholder: bool
    is_mixed_basis: bool


def run_simulation(
    params: Dict[str, Parameter],
    t_horizon: int = 50,
    n_samples: int = 100000,
    k_switch: float = 0.0,
    cost_basis: str = "global_withdrawal",
    seed: int = 42,
    scenario_idx: int = 0,
    allow_mixed_basis: bool = False,
) -> SimulationResults:
    """Execute vectorized Monte Carlo break-even simulation across an (N, T) array."""
    rng = create_scenario_rng(seed, scenario_idx)
    t_steps = np.arange(1, t_horizon + 1)
    pfx = "us" if "us" in cost_basis.lower() else "global"
    keys = _get_active_keys(pfx)
    s, b = sample_parameter_matrix([params[k] for k in keys if k in params], n_samples, rng)
    t = t_steps[np.newaxis, :]
    c = calc_cost(
        s[f"W_direct_{pfx}"][:, None],
        s[f"W_indirect_{pfx}"][:, None],
        k_switch,
        s[f"g_{pfx}"][:, None],
        s[f"G_{pfx}"][:, None],
        t,
    )
    bd = calc_benefit_desal(
        b["s_desal"][:, None],
        s["alpha_desal"][:, None],
        s["D_desal"][:, None],
        s["theta_desal"][:, None],
        s["L_desal"][:, None],
        s["R_desal"][:, None],
        s["rho_desal"][:, None],
        t,
    )
    bf = calc_benefit_solar_food(
        b["s_solar_food"][:, None],
        s["alpha_solar_food"][:, None],
        s["phi_solar_food"][:, None],
        s["A_solar_food"][:, None],
        s["r_solar_food"][:, None],
        s["L_solar_food"][:, None],
        s["R_solar_food"][:, None],
        s["rho_solar_food"][:, None],
        t,
    )
    tot = bd + bf
    nb = calc_net_balance(tot, c)
    cb = params[f"W_direct_{pfx}"].basis
    cost_scope = "scope 1+2 combined" if pfx == "global" else (
        "direct only" if k_switch == 0 else "direct + electricity"
    )
    return SimulationResults(
        t_horizon,
        n_samples,
        cost_basis,
        cost_scope,
        k_switch,
        t_steps,
        nb,
        find_sustained_breakeven(nb),
        find_annual_crossover(tot, c),
        nb[:, -1],
        bd,
        bf,
        s,
        any(params[n].is_placeholder_or_missing for n in keys if n in params),
        cb != "n/a" and cb != params["A_solar_food"].basis,
    )


def compute_summary_metrics(res: SimulationResults) -> Dict[str, Any]:
    """Compute break-even probabilities, MC standard errors, quantiles, and pathway shares."""
    n, be = res.n_samples, res.be_years
    sm: Dict[str, Any] = {
        "n_samples": n,
        "t_horizon": res.t_horizon,
        "cost_basis": res.cost_basis,
        "cost_scope": res.cost_scope,
        "k_switch": res.k_switch,
        "has_placeholder": res.has_placeholder,
        "is_mixed_basis": res.is_mixed_basis,
    }
    for h in [10, 20, 30, 50]:
        if h <= res.t_horizon:
            count = int(np.sum(be <= h))
            _add_probability_metrics(sm, f"breakeven_yr{h}", count, n)
    _add_probability_metrics(sm, "never", int(np.sum(np.isnan(be))), n)
    succ = be[~np.isnan(be)]
    sm["be_year_median"] = float(np.median(succ)) if len(succ) else None
    sm["be_year_p5"] = float(np.percentile(succ, 5)) if len(succ) else None
    sm["be_year_p95"] = float(np.percentile(succ, 95)) if len(succ) else None
    for q in [5, 25, 50, 75, 95]:
        sm[f"n_T_p{q}"] = float(np.percentile(res.final_net_balances, q))
    td, tf = float(np.sum(res.desal_benefits)), float(np.sum(res.solar_food_benefits))
    sm["share_desal_benefit"] = td / (td + tf) if (td + tf) > 0 else 0.0
    sm["share_solar_food_benefit"] = tf / (td + tf) if (td + tf) > 0 else 0.0
    return sm


def wilson_interval(count: int, n_samples: int) -> tuple[float, float]:
    """Return the binomial 95% Wilson interval for a reported Monte Carlo probability."""
    if n_samples <= 0:
        raise ValueError("n_samples must be positive")
    ci = binomtest(count, n_samples).proportion_ci(confidence_level=0.95, method="wilson")
    return float(ci.low), float(ci.high)


def _add_probability_metrics(
    summary: Dict[str, Any], label: str, count: int, n_samples: int
) -> None:
    """Add point estimate, Wilson interval, count, and non-misleading MCSE fields."""
    probability = count / n_samples
    ci_low, ci_high = wilson_interval(count, n_samples)
    # Preserve the established p_breakeven_yrH / mcse_yrH column names.
    suffix = label.removeprefix("breakeven_")
    summary[f"p_{label}"] = probability
    summary[f"ci_low_{suffix}"] = ci_low
    summary[f"ci_high_{suffix}"] = ci_high
    summary[f"count_{suffix}"] = count
    # A zero binomial MCSE is mathematically correct but misleading as a printed uncertainty.
    summary[f"mcse_{suffix}"] = (
        float(np.sqrt(probability * (1.0 - probability) / n_samples))
        if 0 < count < n_samples
        else None
    )


def compute_prcc(sampled_params: Dict[str, np.ndarray], y_target: np.ndarray) -> pd.DataFrame:
    """Compute Partial Rank Correlation Coefficients using inverted Spearman rank matrix."""
    keys = [k for k in sampled_params.keys() if np.std(sampled_params[k]) > 1e-12]
    if not keys:
        return pd.DataFrame(columns=["parameter", "prcc"])
    cols = [rankdata(sampled_params[k]) for k in keys] + [rankdata(y_target)]
    corr = np.corrcoef(np.column_stack(cols), rowvar=False) + np.eye(len(cols)) * 1e-12
    prec = np.linalg.pinv(corr)
    y_idx = len(keys)
    vals = [
        {"parameter": k, "prcc": float(-prec[i, y_idx] / np.sqrt(prec[i, i] * prec[y_idx, y_idx]))}
        for i, k in enumerate(keys)
    ]
    return (
        pd.DataFrame(vals).sort_values(by="prcc", key=abs, ascending=False).reset_index(drop=True)
    )


def compute_tornado(
    params: Dict[str, Parameter],
    t_horizon: int = 50,
    k_switch: float = 0.0,
    cost_basis: str = "global_withdrawal",
) -> pd.DataFrame:
    """Evaluate one-at-a-time low/high sensitivity on final net water balance N(T)."""
    pfx = "us" if "us" in cost_basis.lower() else "global"
    keys = _get_active_keys(pfx)
    b_vals = {k: params[k].mode for k in keys if k in params}
    t = np.arange(1, t_horizon + 1)[np.newaxis, :]

    def ev(p: Dict[str, float]) -> float:
        c = calc_cost(
            p[f"W_direct_{pfx}"], p[f"W_indirect_{pfx}"], k_switch, p[f"g_{pfx}"], p[f"G_{pfx}"], t
        )
        bd = calc_benefit_desal(
            p["p_desal"],
            p["alpha_desal"],
            p["D_desal"],
            p["theta_desal"],
            p["L_desal"],
            p["R_desal"],
            p["rho_desal"],
            t,
        )
        bf = calc_benefit_solar_food(
            p["p_solar_food"],
            p["alpha_solar_food"],
            p["phi_solar_food"],
            p["A_solar_food"],
            p["r_solar_food"],
            p["L_solar_food"],
            p["R_solar_food"],
            p["rho_solar_food"],
            t,
        )
        return float(calc_net_balance(bd + bf, c)[0, -1])

    base = ev(b_vals)
    rows = []
    for k in keys:
        if k in params:
            vl, vh = ev({**b_vals, k: params[k].low}), ev({**b_vals, k: params[k].high})
            rows.append(
                {"parameter": k, "base": base, "val_low": vl, "val_high": vh, "swing": abs(vh - vl)}
            )
    return pd.DataFrame(rows).sort_values(by="swing", ascending=False).reset_index(drop=True)


def compute_conditions_table(
    results: SimulationResults, conditions_horizon: int = 30
) -> pd.DataFrame:
    """Compute parameter medians and IQRs stratified by sustained break-even horizon."""
    mask = (results.be_years <= conditions_horizon) & (~np.isnan(results.be_years))
    rows = []
    for k, v in results.sampled_params.items():
        s, f = v[mask], v[~mask]
        rows.append(
            {
                "parameter": k,
                "conditions_horizon": conditions_horizon,
                "success_median": float(np.median(s)) if len(s) else np.nan,
                "success_iqr": float(np.percentile(s, 75) - np.percentile(s, 25))
                if len(s)
                else np.nan,
                "failure_median": float(np.median(f)) if len(f) else np.nan,
                "failure_iqr": float(np.percentile(f, 75) - np.percentile(f, 25))
                if len(f)
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def check_convergence(
    params: Dict[str, Parameter], n_base: int = 10000, seed: int = 42
) -> Tuple[bool, float, float]:
    """Verify Monte Carlo convergence by comparing estimators at N versus 2N."""
    r1, r2 = (
        run_simulation(params, n_samples=n_base, seed=seed, scenario_idx=0),
        run_simulation(params, n_samples=2 * n_base, seed=seed, scenario_idx=1),
    )
    p1, p2 = float(np.mean(r1.be_years <= 30.0)), float(np.mean(r2.be_years <= 30.0))
    mcse = float(np.sqrt(p1 * (1.0 - p1) / n_base))
    diff = abs(p1 - p2)
    return diff <= max(3.0 * mcse, 1e-4), diff, mcse
