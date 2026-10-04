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
from ai_water_breakeven.sample import create_scenario_rng, sample_inverse_cdf, sample_parameter_matrix

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
    scenario_region, scenario_basis = resolve_region_basis(region or "global", basis, cost_basis)
    active, missing = select_scenario_parameters(params, scenario_region, scenario_basis)
    if missing:
        raise ValueError(
            f"Missing rows for region={scenario_region}, basis={scenario_basis}: {', '.join(missing)}"
        )
    raw_samples, deployments = sample_parameter_matrix(
        list(active.values()), n_samples, create_scenario_rng(seed, scenario_idx)
    )
    return _evaluate_samples(
        active,
        raw_samples,
        deployments,
        t_horizon,
        k_switch,
        scenario_region,
        scenario_basis,
    )


def _evaluate_samples(
    active: Dict[str, Parameter],
    raw_samples: Dict[str, np.ndarray],
    deployments: Dict[str, np.ndarray],
    t_horizon: int,
    k_switch: float,
    scenario_region: str,
    scenario_basis: str,
) -> SimulationResults:
    """Evaluate pre-drawn inputs, keeping sampling separate from scenario modifications."""
    t_steps = np.arange(1, t_horizon + 1)
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
        deployments["s_desal"][:, None],
        s["alpha_desal"][:, None],
        s["D_desal"][:, None],
        s["theta_desal"][:, None],
        s["L_desal"][:, None],
        s["R_desal"][:, None],
        s["rho_desal"][:, None],
        t,
    )
    bf = calc_benefit_solar_food(
        deployments["s_solar_food"][:, None],
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
        len(next(iter(raw_samples.values()))),
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


def _copy_draws(
    samples: Dict[str, np.ndarray], deployments: Dict[str, np.ndarray]
) -> tuple[Dict[str, np.ndarray], Dict[str, np.ndarray]]:
    return ({name: values.copy() for name, values in samples.items()}, {
        name: values.copy() for name, values in deployments.items()
    })


def _set_prefix(
    samples: Dict[str, np.ndarray], active: Dict[str, Parameter], prefix: str, value: float
) -> None:
    """Set every selected pathway parameter whose logical name starts with a prefix."""
    for role, param in active.items():
        if role.startswith(prefix):
            samples[param.name] = np.full_like(samples[param.name], value, dtype=float)


def _set_probability(
    samples: Dict[str, np.ndarray],
    deployments: Dict[str, np.ndarray],
    active: Dict[str, Parameter],
    role: str,
    value: float,
) -> None:
    """Apply a probability override and its deterministic Bernoulli consequence."""
    _set_prefix(samples, active, role, value)
    pathway = "s_desal" if role.endswith("desal") else "s_solar_food"
    deployments[pathway] = np.full_like(deployments[pathway], value, dtype=float)


def _apply_knockout(
    name: str,
    samples: Dict[str, np.ndarray],
    deployments: Dict[str, np.ndarray],
    active: Dict[str, Parameter],
) -> None:
    """Apply one deterministic knockout scenario to copies of the common base draws."""
    if name in {"alpha_1", "ceiling"}:
        _set_prefix(samples, active, "alpha_", 1.0)
    if name in {"success_1", "ceiling"}:
        _set_prefix(samples, active, "p_", 1.0)
        for key in deployments:
            deployments[key] = np.ones_like(deployments[key])
    if name in {"no_rebound", "ceiling"}:
        _set_prefix(samples, active, "rho_", 0.0)
    if name == "no_delay":
        _set_prefix(samples, active, "L_", 0.0)
        _set_prefix(samples, active, "R_", 0.0)
    if name == "flat_cost":
        for role in ("g", "g2"):
            samples[active[role].name] = np.zeros_like(samples[active[role].name])
    if name == "desal_only":
        _set_probability(samples, deployments, active, "p_solar_food", 0.0)
    if name == "solar_food_only":
        _set_probability(samples, deployments, active, "p_desal", 0.0)


KNOCKOUT_SCENARIOS = (
    "baseline",
    "alpha_1",
    "success_1",
    "no_rebound",
    "ceiling",
    "no_delay",
    "flat_cost",
    "desal_only",
    "solar_food_only",
)


def run_knockout_scenarios(
    params: Dict[str, Parameter],
    t_horizon: int = 50,
    n_samples: int = 100000,
    k_switch: float = 0.0,
    seed: int = 42,
    region: str = "global",
    basis: str = "withdrawal",
) -> Dict[str, SimulationResults]:
    """Evaluate deterministic knockout columns against one shared Latin-hypercube draw."""
    active, missing = select_scenario_parameters(params, region, basis)
    if missing:
        raise ValueError(f"Missing rows for region={region}, basis={basis}: {', '.join(missing)}")
    base_samples, base_deployments = sample_parameter_matrix(
        list(active.values()), n_samples, create_scenario_rng(seed, 0)
    )
    results: Dict[str, SimulationResults] = {}
    for name in KNOCKOUT_SCENARIOS:
        samples, deployments = _copy_draws(base_samples, base_deployments)
        _apply_knockout(name, samples, deployments, active)
        results[name] = _evaluate_samples(
            active, samples, deployments, t_horizon, k_switch, region, basis
        )
    return results


def compute_knockout_table(results: Dict[str, SimulationResults]) -> pd.DataFrame:
    """Summarize common-random-number scenarios against the baseline by fixed horizons."""
    baseline = compute_summary_metrics(results["baseline"])
    rows = []
    for name, result in results.items():
        summary = compute_summary_metrics(result)
        row: Dict[str, Any] = {"scenario": name}
        for horizon in [10, 20, 30, 50]:
            if horizon <= result.t_horizon:
                for prefix in ("p_breakeven", "ci_low", "ci_high"):
                    row[f"{prefix}_yr{horizon}"] = summary[f"{prefix}_yr{horizon}"]
        row.update(
            {
                "p_never": summary["p_never"],
                "ci_low_never": summary["ci_low_never"],
                "ci_high_never": summary["ci_high_never"],
                "be_year_median": summary["be_year_median"],
                "n_T_p5": summary["n_T_p5"],
                "n_T_p50": summary["n_T_p50"],
                "n_T_p95": summary["n_T_p95"],
                "change_p_breakeven_yr30_vs_baseline": (
                    summary.get("p_breakeven_yr30", np.nan)
                    - baseline.get("p_breakeven_yr30", np.nan)
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def compute_threshold_map(
    params: Dict[str, Parameter],
    x_name: str,
    y_name: str,
    horizon: int = 30,
    grid: int = 15,
    n_per_cell: int = 5000,
    seed: int = 42,
    k_switch: float = 0.0,
    region: str = "global",
    basis: str = "withdrawal",
) -> pd.DataFrame:
    """Map break-even probability by fixing two columns over shared base draws."""
    if grid < 2:
        raise ValueError("grid must be at least 2")
    active, missing = select_scenario_parameters(params, region, basis)
    if missing:
        raise ValueError(f"Missing rows for region={region}, basis={basis}: {', '.join(missing)}")
    role_by_name = {param.name: role for role, param in active.items()}
    if x_name not in role_by_name or y_name not in role_by_name:
        raise ValueError("Threshold axes must be selected parameters for the requested region and basis")
    x_param, y_param = active[role_by_name[x_name]], active[role_by_name[y_name]]
    x_values = np.linspace(*sample_inverse_cdf(x_param, np.array([0.05, 0.95])), grid)
    y_values = np.linspace(*sample_inverse_cdf(y_param, np.array([0.05, 0.95])), grid)
    base_samples, base_deployments = sample_parameter_matrix(
        list(active.values()), n_per_cell, create_scenario_rng(seed, 17)
    )
    rows = []
    for x_value in x_values:
        for y_value in y_values:
            samples, deployments = _copy_draws(base_samples, base_deployments)
            samples[x_name] = np.full(n_per_cell, x_value)
            samples[y_name] = np.full(n_per_cell, y_value)
            result = _evaluate_samples(
                active, samples, deployments, horizon, k_switch, region, basis
            )
            count = int(np.sum(result.be_years <= horizon))
            ci_low, ci_high = wilson_interval(count, n_per_cell)
            rows.append(
                {
                    "x": x_value,
                    "y": y_value,
                    "P": count / n_per_cell,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "n": n_per_cell,
                }
            )
    return pd.DataFrame(rows)


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
    if count == 0 or count == n_samples:
        summary[f"count_display_{suffix}"] = f"{count} of {n_samples} runs"
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


def compute_net_balance_by_horizon(results: SimulationResults) -> pd.DataFrame:
    """Report baseline cumulative net-balance percentiles at fixed horizons within T."""
    rows = []
    for horizon in [10, 20, 30, 50]:
        if horizon <= results.t_horizon:
            row: Dict[str, Any] = {"horizon": horizon}
            for percentile in [5, 25, 50, 75, 95]:
                row[f"N_p{percentile}"] = float(
                    np.percentile(results.net_balance_trajectories[:, horizon - 1], percentile)
                )
            rows.append(row)
    return pd.DataFrame(rows)


def compute_sourcing_priority(results: SimulationResults) -> pd.DataFrame:
    """Rank sampled inputs by absolute PRCC and retain traceable source metadata."""
    prcc = compute_prcc(results.sampled_params, results.final_net_balances)
    parameter_by_name = {p.name: p for p in results.active_parameters.values()}
    rows = []
    for _, row in prcc.iterrows():
        parameter = parameter_by_name.get(row["parameter"])
        if parameter is None:
            continue
        source_upper = parameter.source.upper()
        status = "MISSING" if "MISSING" in source_upper else (
            "PLACEHOLDER" if "PLACEHOLDER" in source_upper else "sourced"
        )
        abs_prcc = abs(row["prcc"])
        rows.append(
            {
                "parameter": parameter.name,
                "prcc": row["prcc"],
                "abs_prcc": abs_prcc,
                "status": status,
                "confidence": parameter.confidence,
                "source": parameter.source,
                "rank_notice": "Ranks depend on the current input ranges and are provisional.",
                "dominance_warning": bool(abs_prcc > 0.85),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "parameter",
                "prcc",
                "abs_prcc",
                "status",
                "confidence",
                "source",
                "rank_notice",
                "dominance_warning",
            ]
        )
    return pd.DataFrame(rows).sort_values("abs_prcc", ascending=False).reset_index(drop=True)


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
    n_success = int(np.sum(mask))
    n_failure = int(np.sum(~mask))
    rows = []
    for k, v in results.sampled_params.items():
        s, f = v[mask], v[~mask]
        rows.append(
            {
                "parameter": k,
                "conditions_horizon": conditions_horizon,
                "n_success": n_success,
                "n_failure": n_failure,
                "success_median": float(np.median(s)) if len(s) else np.nan,
                "success_iqr": float(np.percentile(s, 75) - np.percentile(s, 25))
                if len(s)
                else np.nan,
                "failure_median": float(np.median(f)) if len(f) else np.nan,
                "failure_iqr": float(np.percentile(f, 75) - np.percentile(f, 25))
                if len(f)
                else np.nan,
                f"success_median_by_{conditions_horizon}yr": float(np.median(s)) if len(s) else np.nan,
                f"success_iqr_by_{conditions_horizon}yr": float(
                    np.percentile(s, 75) - np.percentile(s, 25)
                ) if len(s) else np.nan,
                f"failure_median_by_{conditions_horizon}yr": float(np.median(f)) if len(f) else np.nan,
                f"failure_iqr_by_{conditions_horizon}yr": float(
                    np.percentile(f, 75) - np.percentile(f, 25)
                ) if len(f) else np.nan,
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
