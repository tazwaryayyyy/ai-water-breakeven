"""Tests for Monte Carlo simulation reproducibility, seed sequence streams,
and marginal distributions.
"""

import numpy as np
import pandas as pd
import pytest

from ai_water_breakeven.params import Parameter, load_parameters
from ai_water_breakeven.sample import sample_inverse_cdf, sample_parameter_matrix
from ai_water_breakeven.simulate import (
    SimulationResults,
    compute_conditional_table,
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

    res_a = run_simulation(base_params, t_horizon=30, n_samples=n_runs, seed=42)
    res_b = run_simulation(base_params, t_horizon=30, n_samples=n_runs, seed=42)
    np.testing.assert_allclose(res_a.net_balance_trajectories, res_b.net_balance_trajectories)
    np.testing.assert_allclose(res_a.be_years, res_b.be_years, equal_nan=True)

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

    p_uni = Parameter(
        "x_u", "", "", "n/a", "", 2027, "uniform", 100.0, 300.0, 500.0, "P", "", "C", ""
    )
    s_uni = sample_inverse_cdf(p_uni, u)
    assert np.isclose(np.percentile(s_uni, 50), 300.0, rtol=0.03)
    assert np.isclose(np.percentile(s_uni, 25), 200.0, rtol=0.03)

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


def test_threshold_map_has_expected_monotonic_directions(synthetic_params):
    """Shared-draw threshold cells are monotonic with a synthetic parameter set."""
    table = compute_threshold_map(
        synthetic_params(),
        "g_global",
        "phi_solar_food",
        horizon=20,
        grid=3,
        n_per_cell=400,
        seed=23,
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
    """A synthetic parameter set with A fixed at 0 has 0 solar_food share
    and carries basis_notice; with A > 0 it does not.
    """
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

    res_pos = run_simulation(base_params, t_horizon=20, n_samples=500, seed=42)
    sm_pos = compute_summary_metrics(res_pos)
    assert "basis_notice" not in sm_pos or sm_pos.get("basis_notice") is None
    assert sm_pos["share_solar_food_benefit"] > 0.0


def test_sourcing_priority_status_synthetic_rows():
    """compute_sourcing_priority sets status to assumption for confidence C
    with real source, sourced for A/B, and preserves PLACEHOLDER/MISSING.
    """
    n = 100
    rng = np.random.default_rng(42)
    params = {
        "p_c_sourced": Parameter(
            "p_c_sourced",
            "",
            "",
            "withdrawal",
            "global",
            2024,
            "uniform",
            0.1,
            0.2,
            0.3,
            "Empirical Report 2024",
            "Table 1",
            "C",
            "",
        ),
        "p_a_sourced": Parameter(
            "p_a_sourced",
            "",
            "",
            "withdrawal",
            "global",
            2024,
            "uniform",
            0.1,
            0.2,
            0.3,
            "Peer Reviewed Study",
            "Table 2",
            "A",
            "",
        ),
        "p_b_sourced": Parameter(
            "p_b_sourced",
            "",
            "",
            "withdrawal",
            "global",
            2024,
            "uniform",
            0.1,
            0.2,
            0.3,
            "Agency Report",
            "p. 5",
            "B",
            "",
        ),
        "p_placeholder": Parameter(
            "p_placeholder",
            "",
            "",
            "withdrawal",
            "global",
            2024,
            "uniform",
            0.1,
            0.2,
            0.3,
            "PLACEHOLDER",
            "",
            "C",
            "",
        ),
        "p_missing": Parameter(
            "p_missing",
            "",
            "",
            "withdrawal",
            "global",
            2024,
            "uniform",
            0.1,
            0.2,
            0.3,
            "MISSING",
            "",
            "C",
            "",
        ),
    }
    sampled = {k: rng.uniform(0.1, 0.3, n) for k in params}
    y = rng.normal(0, 1, n)

    # Create varied benefit trajectories and break-even years so correlation computation works
    desal_benefits = rng.uniform(0, 1, (n, 10))
    solar_food_benefits = rng.uniform(0, 1, (n, 10))
    be_years = rng.choice([5.0, 10.0, np.nan], size=n)

    deployments = {
        "s_desal": rng.choice([0.0, 1.0], size=n),
        "s_solar_food": rng.choice([0.0, 1.0], size=n),
    }

    results = SimulationResults(
        t_horizon=10,
        n_samples=n,
        cost_basis="global_withdrawal",
        region="global",
        basis="withdrawal",
        cost_scope="direct",
        k_switch=0.0,
        time_steps=np.arange(1, 11),
        net_balance_trajectories=np.zeros((n, 10)),
        be_years=be_years,
        crossover_years=np.full(n, np.nan),
        final_net_balances=y,
        desal_benefits=desal_benefits,
        solar_food_benefits=solar_food_benefits,
        cost_trajectories=np.zeros((n, 10)),
        cost_at_zero=np.ones(n),
        sampled_params=sampled,
        active_parameters=params,
        has_placeholder=True,
        is_mixed_basis=False,
        deployments=deployments,
    )
    df = compute_sourcing_priority(results)
    status_map = dict(zip(df["parameter"], df["status"]))
    assert status_map["p_c_sourced"] == "assumption"
    assert status_map["p_a_sourced"] == "sourced"
    assert status_map["p_b_sourced"] == "sourced"
    assert status_map["p_placeholder"] == "PLACEHOLDER"
    assert status_map["p_missing"] == "MISSING"

    assert "s_desal" in df["parameter"].values
    assert "s_solar_food" in df["parameter"].values


def test_deployment_draw_determines_breakeven_correlation(synthetic_params):
    """Test (a): In a synthetic parameter set where one pathway's deployment draw
    fully determines break-even, s_<pathway> has the highest abs_corr_breakeven.
    """
    n = 1000

    # Synthetic set: desal always deployed and strong, so solar_food deployment decides break-even
    params = synthetic_params(
        {
            "g_global": ("fixed", 0.0, 0.0, 0.0),
            "p_desal": ("fixed", 1.0, 1.0, 1.0),
            "rho_desal": ("fixed", 0.0, 0.0, 0.0),
            "L_desal": ("fixed", 0.0, 0.0, 0.0),
            "R_desal": ("fixed", 0.0, 0.0, 0.0),
            "D_desal": ("fixed", 1.0e10, 1.0e10, 1.0e10),
            "theta_desal": ("fixed", 0.10, 0.10, 0.10),
            "p_solar_food": ("uniform", 0.0, 0.5, 1.0),
            "alpha_solar_food": ("fixed", 1.0, 1.0, 1.0),
            "rho_solar_food": ("fixed", 0.0, 0.0, 0.0),
            "L_solar_food": ("fixed", 0.0, 0.0, 0.0),
            "R_solar_food": ("fixed", 0.0, 0.0, 0.0),
            "phi_solar_food": ("fixed", 0.05, 0.05, 0.05),
            "A_solar_food": ("fixed", 2.0e12, 2.0e12, 2.0e12),
            "r_solar_food": ("fixed", 0.0, 0.0, 0.0),
        }
    )

    res = run_simulation(params, t_horizon=30, n_samples=n, seed=42)
    df = compute_sourcing_priority(res)

    top_param = df.iloc[0]["parameter"]
    assert top_param == "s_solar_food", f"Expected s_solar_food to be top, got {top_param}"
    assert df.iloc[0]["abs_corr_breakeven"] > 0.7


def test_threshold_with_log_spacing_and_range(synthetic_params):
    """Test (b): threshold with --x-range 0.001 0.5 --log gives grid values
    inside the range with a constant ratio between neighbours.
    """
    params = synthetic_params(
        {
            "alpha_solar_food": ("triangular", 0.001, 0.1, 0.5),
            "phi_solar_food": ("triangular", 0.001, 0.05, 0.13),
        }
    )

    table = compute_threshold_map(
        params,
        "alpha_solar_food",
        "phi_solar_food",
        horizon=20,
        grid=5,
        n_per_cell=200,
        seed=23,
        x_range=(0.001, 0.5),
        y_range=(0.001, 0.13),
        log_spacing=True,
    )

    x_values = np.sort(table["x"].unique())
    y_values = np.sort(table["y"].unique())

    assert np.isclose(x_values[0], 0.001, rtol=0.01)
    assert np.isclose(x_values[-1], 0.5, rtol=0.01)

    assert np.isclose(y_values[0], 0.001, rtol=0.01)
    assert np.isclose(y_values[-1], 0.13, rtol=0.01)

    x_ratios = x_values[1:] / x_values[:-1]
    assert np.allclose(x_ratios, x_ratios[0], rtol=0.01)

    y_ratios = y_values[1:] / y_values[:-1]
    assert np.allclose(y_ratios, y_ratios[0], rtol=0.01)


def test_threshold_default_unchanged(base_params):
    """Test (c): default threshold output is unchanged."""
    table_default = compute_threshold_map(
        base_params, "g_global", "phi_solar_food", horizon=30, grid=3, n_per_cell=200, seed=42
    )

    table_explicit = compute_threshold_map(
        base_params,
        "g_global",
        "phi_solar_food",
        horizon=30,
        grid=3,
        n_per_cell=200,
        seed=42,
        x_range=None,
        y_range=None,
        log_spacing=False,
    )

    pd.testing.assert_frame_equal(table_default, table_explicit)


def test_deployments_captured_with_zero_benefit(synthetic_params):
    """With A_solar_food fixed at 0 and p_solar_food fixed at 1,
    results.deployments['s_solar_food'] is all ones.
    """
    n = 100
    params = synthetic_params(
        {
            "g_global": ("fixed", 0.0, 0.0, 0.0),
            "p_desal": ("fixed", 0.5, 0.5, 0.5),
            "rho_desal": ("fixed", 0.0, 0.0, 0.0),
            "L_desal": ("fixed", 0.0, 0.0, 0.0),
            "R_desal": ("fixed", 0.0, 0.0, 0.0),
            "D_desal": ("fixed", 1.0e10, 1.0e10, 1.0e10),
            "theta_desal": ("fixed", 0.10, 0.10, 0.10),
            "p_solar_food": ("fixed", 1.0, 1.0, 1.0),
            "alpha_solar_food": ("fixed", 1.0, 1.0, 1.0),
            "rho_solar_food": ("fixed", 0.0, 0.0, 0.0),
            "L_solar_food": ("fixed", 0.0, 0.0, 0.0),
            "R_solar_food": ("fixed", 0.0, 0.0, 0.0),
            "phi_solar_food": ("fixed", 0.05, 0.05, 0.05),
            "A_solar_food": ("fixed", 0.0, 0.0, 0.0),
            "r_solar_food": ("fixed", 0.0, 0.0, 0.0),
        }
    )

    res = run_simulation(params, t_horizon=10, n_samples=n, seed=42)

    # Even though benefit is zero, deployment draw should be all ones (p=1.0)
    assert "s_solar_food" in res.deployments
    assert np.all(res.deployments["s_solar_food"] == 1.0)


def _conditional_results(be_years, deployments, t_horizon=50):
    n = len(be_years)
    return SimulationResults(
        t_horizon=t_horizon,
        n_samples=n,
        cost_basis="global_consumption",
        region="global",
        basis="consumption",
        cost_scope="scope 1+2 combined",
        k_switch=0.0,
        time_steps=np.arange(1, t_horizon + 1),
        net_balance_trajectories=np.zeros((n, t_horizon)),
        be_years=np.asarray(be_years, dtype=float),
        crossover_years=np.full(n, np.nan),
        final_net_balances=np.zeros(n),
        desal_benefits=np.zeros((n, t_horizon)),
        solar_food_benefits=np.zeros((n, t_horizon)),
        cost_trajectories=np.zeros((n, t_horizon)),
        cost_at_zero=np.ones(n),
        sampled_params={},
        active_parameters={},
        has_placeholder=True,
        is_mixed_basis=False,
        deployments=deployments,
    )


def test_conditional_table_hand_computed():
    """Deployed solar-food runs are indices 0-3 with break-even years 5, 10, never, 20."""
    res = _conditional_results(
        [5, 10, np.nan, 20, 3, 4, 5, 6, 7, 8],
        {"s_solar_food": np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=float)},
    )
    df = compute_conditional_table(res)
    assert list(df["pathway"]) == ["solar_food", "desal", "any"]
    row = df.set_index("pathway").loc["solar_food"]
    assert row["n_deployed"] == 4
    assert row["p_deploy"] == 0.4
    assert row["count_yr10"] == 2
    assert row["p_breakeven_yr10"] == 0.5
    assert row["p_breakeven_yr20"] == 0.75
    assert row["p_breakeven_yr30"] == 0.75
    assert row["p_breakeven_yr50"] == 0.75
    assert row["p_never"] == 0.25
    assert row["be_year_median"] == 10.0
    assert row["ci_low_yr10"] < row["p_breakeven_yr10"] < row["ci_high_yr10"]


def test_conditional_table_any_uses_or():
    """The any row deploys where either pathway draw is 1 (indices 0,1,2,3,5,6)."""
    res = _conditional_results(
        [5, 10, np.nan, 20, 3, 4, 5, 6, 7, 8],
        {
            "s_solar_food": np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=float),
            "s_desal": np.array([0, 0, 0, 0, 0, 1, 1, 0, 0, 0], dtype=float),
        },
    )
    df = compute_conditional_table(res).set_index("pathway")
    row = df.loc["any"]
    assert row["n_deployed"] == 6
    assert row["p_deploy"] == 0.6
    assert row["count_yr10"] == 4
    assert row["p_breakeven_yr10"] == pytest.approx(4 / 6)
    assert row["p_breakeven_yr20"] == pytest.approx(5 / 6)
    assert row["p_never"] == pytest.approx(1 / 6)
    assert row["be_year_median"] == 5.0
    desal = df.loc["desal"]
    assert desal["n_deployed"] == 2
    assert desal["p_breakeven_yr10"] == 1.0
    assert desal["be_year_median"] == 4.5


def test_conditional_table_empty_deployments():
    res = _conditional_results([5, np.nan], {})
    df = compute_conditional_table(res)
    assert df.empty
    for column in [
        "pathway",
        "n_deployed",
        "p_deploy",
        "p_breakeven_yr10",
        "p_never",
        "be_year_median",
        "be_year_p5",
        "be_year_p95",
    ]:
        assert column in df.columns
