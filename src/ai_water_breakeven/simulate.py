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
from ai_water_breakeven.params import Parameter, resolve_region_basis, select_scenario_parameters
from ai_water_breakeven.sample import create_scenario_rng, sample_parameter_matrix

@dataclass
class SimulationResults:
    t_horizon: int
    n_samples: int
    cost_basis: str
    region: str
    basis: str
    cost_scope: str
    k_switch: float
    time_steps: np.ndarray
    net_balance_trajectories: np.ndarray
    be_years: np.ndarray
    crossover_years: np.ndarray
    final_net_balances: np.ndarray
    desal_benefits: np.ndarray
    solar_food_benefits: np.ndarray
    cost_trajectories: np.ndarray
    cost_at_zero: np.ndarray
    sampled_params: Dict[str, np.ndarray]
    active_parameters: Dict[str, Parameter]
    has_placeholder: bool
    is_mixed_basis: bool


def run_simulation(
    params: Dict[str, Parameter],
    t_horizon: int = 50,
    n_samples: int = 100000,
    k_switch: float = 0.0,
    cost_basis: str | None = None,
    seed: int = 42,
    scenario_idx: int = 0,
    allow_mixed_basis: bool = False,
    region: str | None = None,
    basis: str = "withdrawal",
) -> SimulationResults:
    """Execute vectorized Monte Carlo break-even simulation across an (N, T) array."""
    rng = create_scenario_rng(seed, scenario_idx)
    t_steps = np.arange(1, t_horizon + 1)
    scenario_region, scenario_basis = resolve_region_basis(region or "global", basis, cost_basis)
    active, missing = select_scenario_parameters(params, scenario_region, scenario_basis)
    if missing:
        raise ValueError(
            f"Missing rows for region={scenario_region}, basis={scenario_basis}: {', '.join(missing)}"
        )
    raw_samples, b = sample_parameter_matrix(list(active.values()), n_samples, rng)
    s = {role: raw_samples[p.name] for role, p in active.items()}
    t = t_steps[np.newaxis, :]
    c = calc_cost(
        s["W_direct"][:, None],
        s["W_indirect"][:, None],
        1.0 if scenario_region == "global" else k_switch,
        s["g"][:, None],
        s["G"][:, None],
        s["g2"][:, None],
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
    cost_scope = "scope 1+2 combined" if scenario_region == "global" else (
        "direct only" if k_switch == 0 else "direct + electricity"
    )
    return SimulationResults(
        t_horizon,
        n_samples,
        f"{scenario_region}_{scenario_basis}",
        scenario_region,
        scenario_basis,
        cost_scope,
        k_switch,
        t_steps,
        nb,
        find_sustained_breakeven(nb),
        find_annual_crossover(tot, c),
        nb[:, -1],
        bd,
        bf,
        c,
        s["W_direct"] + (1.0 if scenario_region == "global" else k_switch) * s["W_indirect"],
        raw_samples,
        active,
        any(p.is_placeholder_or_missing for p in active.values()),
        False,
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


def compute_cost_trajectory(results: SimulationResults) -> pd.DataFrame:
    """Report C(t) and C(t)/C(0) percentiles at predefined comparison years."""
    rows = []
    for year in [5, 10, 25, 50]:
        if year <= results.t_horizon:
            cost = results.cost_trajectories[:, year - 1]
            ratio = np.divide(
                cost,
                results.cost_at_zero,
                out=np.full_like(cost, np.nan),
                where=results.cost_at_zero != 0,
            )
            row: Dict[str, Any] = {"year": year}
            for percentile in [5, 25, 50, 75, 95]:
                row[f"C_p{percentile}"] = float(np.nanpercentile(cost, percentile))
                row[f"C_over_C0_p{percentile}"] = float(np.nanpercentile(ratio, percentile))
            rows.append(row)
    return pd.DataFrame(rows)


def compute_tornado(
    params: Dict[str, Parameter],
    t_horizon: int = 50,
    k_switch: float = 0.0,
    cost_basis: str | None = None,
    region: str | None = None,
    basis: str = "withdrawal",
) -> pd.DataFrame:
    """Evaluate one-at-a-time low/high sensitivity on final net water balance N(T)."""
    scenario_region, scenario_basis = resolve_region_basis(region or "global", basis, cost_basis)
    active, missing = select_scenario_parameters(params, scenario_region, scenario_basis)
    if missing:
        raise ValueError(
            f"Missing rows for region={scenario_region}, basis={scenario_basis}: {', '.join(missing)}"
        )
    b_vals = {k: p.mode for k, p in active.items()}
    t = np.arange(1, t_horizon + 1)[np.newaxis, :]

    def ev(p: Dict[str, float]) -> float:
        c = calc_cost(
            p["W_direct"],
            p["W_indirect"],
            1.0 if scenario_region == "global" else k_switch,
            p["g"],
            p["G"],
            p["g2"],
            t,
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
    for k, param in active.items():
        if k in active:
            vl, vh = ev({**b_vals, k: param.low}), ev({**b_vals, k: param.high})
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
