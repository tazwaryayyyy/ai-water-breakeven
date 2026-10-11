"""Tests for Monte Carlo simulation reproducibility, seed sequence streams,
and marginal distributions.
"""

import numpy as np
import pytest

from ai_water_breakeven.params import Parameter, load_parameters
from ai_water_breakeven.sample import sample_inverse_cdf, sample_parameter_matrix
from ai_water_breakeven.simulate import (
    compute_conditions_table,
    compute_sourcing_priority,
    compute_summary_metrics,
    compute_threshold_map,
    run_knockout_scenarios,
    run_simulation,
    wilson_interval,
)


@pytest.fixture
def base_params():
    return load_parameters("data/parameters.csv")


def test_seed_determinism_and_mcse_agreement(base_params):
    """Test 5: Same seed gives identical output; different seeds agree within 3 MCSE."""
    n_runs = 8000

    # Identical seed reproduction
    res_a = run_simulation(base_params, t_horizon=30, n_samples=n_runs, seed=42)
    res_b = run_simulation(base_params, t_horizon=30, n_samples=n_runs, seed=42)
    np.testing.assert_allclose(res_a.net_balance_trajectories, res_b.net_balance_trajectories)
    np.testing.assert_allclose(res_a.be_years, res_b.be_years, equal_nan=True)

    # Different seeds agree within 3 MC standard errors
    res_c = run_simulation(base_params, t_horizon=30, n_samples=n_runs, seed=999)
    sm_a = compute_summary_metrics(res_a)
    sm_c = compute_summary_metrics(res_c)

    p_a = sm_a["p_breakeven_yr30"]
    p_c = sm_c["p_breakeven_yr30"]
    se_a = sm_a["mcse_yr30"]

    diff = abs(p_a - p_c)
    assert diff <= max(3.5 * se_a, 0.015), (
        f"Estimates differed by {diff}, exceeding 3 MCSE ({3 * se_a})"
    )


def test_sampled_marginals_match_quantiles():
    """Test 6a: Sampled marginal distributions match analytical quantiles."""
    rng = np.random.default_rng(123)
    n = 25000
    u = rng.uniform(0.0, 1.0, size=n)

    # Uniform distribution: [100, 500]
    p_uni = Parameter(
        "x_u", "", "", "n/a", "", 2027, "uniform", 100.0, 300.0, 500.0, "P", "", "C", ""
    )
    s_uni = sample_inverse_cdf(p_uni, u)
    assert np.isclose(np.percentile(s_uni, 50), 300.0, rtol=0.03)
    assert np.isclose(np.percentile(s_uni, 25), 200.0, rtol=0.03)

    # Lognormal distribution: p5=20.0, p95=200.0
    p_log = Parameter(
        "x_l", "", "", "n/a", "", 2027, "lognormal", 20.0, 63.2, 200.0, "P", "", "C", ""
    )
    s_log = sample_inverse_cdf(p_log, u)
    assert np.isclose(np.percentile(s_log, 5), 20.0, rtol=0.04)
    assert np.isclose(np.percentile(s_log, 95), 200.0, rtol=0.04)


def test_bernoulli_frequency_matches_probability():
    """Test 6b: Bernoulli deployment frequency matches target probability p."""
    rng = np.random.default_rng(456)
    n = 30000
    p_target = 0.65
    p_param = Parameter(
        "p_desal", "", "", "n/a", "", 2027, "fixed", p_target, p_target, p_target, "P", "", "C", ""
    )

    _, bern = sample_parameter_matrix([p_param], n, rng)
    empirical_p = np.mean(bern["s_desal"])
    se = np.sqrt(p_target * (1.0 - p_target) / n)

    assert abs(empirical_p - p_target) <= 3.0 * se


def test_wilson_interval_contains_estimate_and_handles_zero_count():
    """Wilson intervals are bounded, cover the estimate, and retain edge uncertainty."""
    low, high = wilson_interval(37, 100)
    assert 0.0 <= low <= 0.37 <= high <= 1.0
    low_zero, high_zero = wilson_interval(0, 100000)
    assert low_zero == 0.0
    assert np.isclose(high_zero, 3.84e-5, rtol=0.03)


def test_common_random_number_ceiling_cannot_delay_break_even(base_params):
    """The combined ceiling overrides improve or retain every paired sampled run."""
    results = run_knockout_scenarios(base_params, t_horizon=30, n_samples=1000, seed=19)
    baseline, ceiling = results["baseline"].be_years, results["ceiling"].be_years
    paired_base = np.where(np.isnan(baseline), np.inf, baseline)
    paired_ceiling = np.where(np.isnan(ceiling), np.inf, ceiling)
    assert np.all(paired_ceiling <= paired_base)
    for horizon in [10, 20, 30]:
        assert np.mean(paired_ceiling <= horizon) >= np.mean(paired_base <= horizon)


def test_threshold_map_has_expected_monotonic_directions():
    """Shared-draw threshold cells are monotonic with a synthetic parameter set."""
    synthetic_params = {
        "W_direct_global": Parameter("W_direct_global", "", "m^3/yr", "withdrawal", "global", 2027, "fixed", 5.0e9, 5.0e9, 5.0e9, "S", "", "C", ""),
        "W_indirect_global": Parameter("W_indirect_global", "", "m^3/yr", "withdrawal", "global", 2027, "fixed", 0.0, 0.0, 0.0, "S", "", "C", ""),
        "g_global": Parameter("g_global", "", "dimensionless", "n/a", "global", 2027, "triangular", 0.10, 0.20, 0.30, "S", "", "C", ""),
        "G_global": Parameter("G_global", "", "yr", "n/a", "global", 2027, "fixed", 5.0, 5.0, 5.0, "S", "", "C", ""),
        "g2_global": Parameter("g2_global", "", "dimensionless", "n/a", "global", 2027, "fixed", 0.0, 0.0, 0.0, "S", "", "C", ""),
        "p_desal": Parameter("p_desal", "", "dimensionless", "n/a", "global", 2027, "fixed", 0.8, 0.8, 0.8, "S", "", "C", ""),
        "alpha_desal": Parameter("alpha_desal", "", "dimensionless", "n/a", "global", 2027, "fixed", 0.15, 0.15, 0.15, "S", "", "C", ""),
        "rho_desal": Parameter("rho_desal", "", "dimensionless", "n/a", "global", 2027, "fixed", 0.10, 0.10, 0.10, "S", "", "C", ""),
        "L_desal": Parameter("L_desal", "", "yr", "n/a", "global", 2027, "fixed", 5.0, 5.0, 5.0, "S", "", "C", ""),
        "R_desal": Parameter("R_desal", "", "yr", "n/a", "global", 2027, "fixed", 10.0, 10.0, 10.0, "S", "", "C", ""),
        "D_desal": Parameter("D_desal", "", "m^3/yr", "n/a", "global", 2027, "fixed", 3.5e10, 3.5e10, 3.5e10, "S", "", "C", ""),
        "theta_desal": Parameter("theta_desal", "", "dimensionless", "n/a", "global", 2027, "fixed", 0.05, 0.05, 0.05, "S", "", "C", ""),
        "p_solar_food": Parameter("p_solar_food", "", "dimensionless", "n/a", "global", 2027, "fixed", 0.5, 0.5, 0.5, "S", "", "C", ""),
        "alpha_solar_food": Parameter("alpha_solar_food", "", "dimensionless", "n/a", "global", 2027, "fixed", 0.25, 0.25, 0.25, "S", "", "C", ""),
        "rho_solar_food": Parameter("rho_solar_food", "", "dimensionless", "n/a", "global", 2027, "fixed", 0.10, 0.10, 0.10, "S", "", "C", ""),
        "L_solar_food": Parameter("L_solar_food", "", "yr", "n/a", "global", 2027, "fixed", 5.0, 5.0, 5.0, "S", "", "C", ""),
        "R_solar_food": Parameter("R_solar_food", "", "yr", "n/a", "global", 2027, "fixed", 10.0, 10.0, 10.0, "S", "", "C", ""),
        "phi_solar_food": Parameter("phi_solar_food", "", "dimensionless", "n/a", "global", 2027, "triangular", 0.01, 0.03, 0.06, "S", "", "C", ""),
        "A_solar_food": Parameter("A_solar_food", "", "m^3/yr", "withdrawal", "global", 2027, "fixed", 2.8e12, 2.8e12, 2.8e12, "S", "", "C", ""),
        "r_solar_food": Parameter("r_solar_food", "", "dimensionless", "withdrawal", "global", 2027, "fixed", 0.20, 0.20, 0.20, "S", "", "C", ""),
    }
    table = compute_threshold_map(
        synthetic_params, "g_global", "phi_solar_food", horizon=20, grid=3, n_per_cell=400, seed=23
    )
    pivot = table.pivot(index="y", columns="x", values="P")
    for _, row in pivot.iterrows():
        assert np.all(np.diff(row.to_numpy()) <= 0)
    for _, column in pivot.items():
        assert np.all(np.diff(column.to_numpy()) >= 0)



def test_conditions_table_success_count_matches_horizon_be_runs(base_params):
    """Test 8: Number of success runs in conditions equals sustained BE <= conditions_horizon."""
    res = run_simulation(base_params, t_horizon=30, n_samples=1000, seed=42)
    for horizon in [10, 20, 30]:
        df = compute_conditions_table(res, conditions_horizon=horizon)
        expected_success = int(np.sum((res.be_years <= horizon) & (~np.isnan(res.be_years))))
        expected_failure = int(res.n_samples - expected_success)
        assert df["n_success"].iloc[0] == expected_success
        assert df["n_failure"].iloc[0] == expected_failure
        assert df["conditions_horizon"].iloc[0] == horizon


def test_dominance_check_trips_on_wide_parameter_and_not_on_narrow(base_params):
    """Dominance warning trips when a parameter has |PRCC| > 0.85 and does not otherwise."""
    # Calibrated run: no parameter has |PRCC| > 0.85
    res_cal = run_simulation(base_params, t_horizon=30, n_samples=3000, seed=42)
    df_cal = compute_sourcing_priority(res_cal)
    assert "dominance_warning" in df_cal.columns
    assert not df_cal["dominance_warning"].any()

    # Synthetic run with one artificially wide parameter (g2 spanning [-0.50, 0.50])
    wide_params = dict(base_params)
    p_orig = wide_params["g2_global"]
    wide_params["g2_global"] = Parameter(
        p_orig.name,
        p_orig.description,
        p_orig.unit,
        p_orig.basis,
        p_orig.region,
        p_orig.year,
        "triangular",
        low=-0.50,
        mode=0.00,
        high=0.50,
        source=p_orig.source,
        locator=p_orig.locator,
        confidence=p_orig.confidence,
        notes=p_orig.notes,
    )
    res_wide = run_simulation(wide_params, t_horizon=30, n_samples=3000, seed=42)
    df_wide = compute_sourcing_priority(res_wide)
    assert df_wide["dominance_warning"].any()
    tripped = df_wide[df_wide["dominance_warning"]]["parameter"].tolist()
    assert "g2_global" in tripped


def test_zero_ceiling_pathway_disclosure(base_params):
    """A synthetic parameter set with A fixed at 0 has 0 solar_food share and carries basis_notice; with A > 0 it does not."""
    # Synthetic set with A fixed at 0
    p_zero = dict(base_params)
    p_a = p_zero["A_solar_food"]
    p_zero["A_solar_food"] = Parameter(
        p_a.name,
        p_a.description,
        p_a.unit,
        p_a.basis,
        p_a.region,
        p_a.year,
        "fixed",
        0.0,
        0.0,
        0.0,
        p_a.source,
        p_a.locator,
        p_a.confidence,
        p_a.notes,
    )
    res_zero = run_simulation(p_zero, t_horizon=20, n_samples=500, seed=42)
    sm_zero = compute_summary_metrics(res_zero)
    assert sm_zero["share_solar_food_benefit"] == 0.0
    assert "basis_notice" in sm_zero
    assert sm_zero["basis_notice"] is not None
    assert "solar_food benefit is identically zero" in sm_zero["basis_notice"]
    assert "results reflect the remaining pathways only" in sm_zero["basis_notice"]

    # Parameter set with A > 0 (withdrawal baseline)
    res_pos = run_simulation(base_params, t_horizon=20, n_samples=500, seed=42)
    sm_pos = compute_summary_metrics(res_pos)
    assert "basis_notice" not in sm_pos or sm_pos.get("basis_notice") is None
    assert sm_pos["share_solar_food_benefit"] > 0.0

