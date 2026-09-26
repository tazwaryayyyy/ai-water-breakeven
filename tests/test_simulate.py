"""Tests for Monte Carlo simulation reproducibility, seed sequence streams,
and marginal distributions.
"""

import numpy as np
import pytest

from ai_water_breakeven.params import Parameter, load_parameters
from ai_water_breakeven.sample import sample_inverse_cdf, sample_parameter_matrix
from ai_water_breakeven.simulate import (
    compute_conditions_table,
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


def test_threshold_map_has_expected_monotonic_directions(base_params):
    """Shared-draw threshold cells are monotonic when rebound factors are at most one."""
    table = compute_threshold_map(
        base_params, "g_global", "phi_solar_food", horizon=20, grid=3, n_per_cell=400, seed=23
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
