"""Tests for core physical and financial equations, toy cases, and monotonicity."""

import numpy as np

from ai_water_breakeven.model import (
    M3_PER_US_GALLON,
    calc_benefit_desal,
    calc_benefit_solar_food,
    calc_cost,
    calc_net_balance,
    calc_ramp,
    find_sustained_breakeven,
    gallons_to_m3,
    m3_to_gallons,
)


def _eval_single_pathway(
    t_max: int = 100,
    cost_val: float = 10.0,
    g_val: float = 0.0,
    G_val: float = 100.0,
    s_val: float = 1.0,
    alpha_val: float = 1.0,
    gross_val: float = 30.0,
    ramp_val: float = 0.0,
    lag_val: float = 10.0,
    rho_val: float = 0.5,
) -> float:
    t = np.arange(1, t_max + 1)
    c = calc_cost(
        np.array([cost_val]),
        np.array([0.0]),
        0.0,
        np.array([g_val]),
        np.array([G_val]),
        t[np.newaxis, :],
    )
    ramp = calc_ramp(t[np.newaxis, :], np.array([[lag_val]]), np.array([[ramp_val]]))
    b = s_val * alpha_val * gross_val * ramp * (1.0 - rho_val)
    nb = calc_net_balance(b, c)
    return float(find_sustained_breakeven(nb)[0])


def test_toy_case_exact_reproduction():
    """Toy case test 1: T=100, C=10/yr, g=0; Gross=30, R=0."""
    # Base configuration gives break-even year 30
    be_base = _eval_single_pathway(t_max=100, lag_val=10.0, rho_val=0.5)
    assert be_base == 30.0

    # L = 20 gives break-even year 60
    be_lag20 = _eval_single_pathway(t_max=100, lag_val=20.0, rho_val=0.5)
    assert be_lag20 == 60.0

    # rho = 0 (with L = 10) gives break-even year 15
    be_rho0 = _eval_single_pathway(t_max=100, lag_val=10.0, rho_val=0.0)
    assert be_rho0 == 15.0


def test_zero_benefit_and_zero_cost_edges():
    """Test 2: Zero benefit gives 'never'; zero cost gives year 1."""
    t = np.arange(1, 51)

    # Zero benefit with positive cost yields never
    c_pos = calc_cost(
        np.array([10.0]), np.array([0.0]), 0.0, np.array([0.0]), np.array([50.0]), t[np.newaxis, :]
    )
    b_zero = np.zeros_like(c_pos)
    nb_no_benefit = calc_net_balance(b_zero, c_pos)
    assert np.isnan(find_sustained_breakeven(nb_no_benefit)[0])

    # Zero cost with non-negative benefit yields year 1
    c_zero = np.zeros_like(c_pos)
    b_pos = np.full_like(c_pos, 5.0)
    nb_zero_cost = calc_net_balance(b_pos, c_zero)
    assert find_sustained_breakeven(nb_zero_cost)[0] == 1.0


def test_monotonicity_on_grid():
    """Test 3: Raising rho, L, R, g never lowers BE year; raising alpha, Gross never raises it."""
    base_params = {
        "cost_val": 10.0,
        "g_val": 0.0,
        "s_val": 1.0,
        "alpha_val": 0.8,
        "gross_val": 40.0,
        "ramp_val": 2.0,
        "lag_val": 5.0,
        "rho_val": 0.2,
    }
    base_be = _eval_single_pathway(**base_params)

    # Raising friction/cost parameters (rho, L, R, g) must not lower the break-even year
    for p_name, incr in [("rho_val", 0.2), ("lag_val", 5.0), ("ramp_val", 5.0), ("g_val", 0.05)]:
        test_kwargs = dict(base_params)
        test_kwargs[p_name] += incr
        new_be = _eval_single_pathway(**test_kwargs)
        # If new_be is NaN, it never broke even (effectively +infinity, which is >= base_be)
        if not np.isnan(new_be):
            assert new_be >= base_be, (
                f"Raising {p_name} unexpectedly lowered BE year from {base_be} to {new_be}"
            )

    # Raising benefit parameters (alpha, Gross) must not raise the break-even year
    for p_name, incr in [("alpha_val", 0.15), ("gross_val", 20.0)]:
        test_kwargs = dict(base_params)
        test_kwargs[p_name] += incr
        new_be = _eval_single_pathway(**test_kwargs)
        assert not np.isnan(new_be), f"Raising {p_name} caused simulation to never break even"
        assert new_be <= base_be, (
            f"Raising {p_name} unexpectedly increased BE year from {base_be} to {new_be}"
        )


def test_gallons_to_m3_conversion_round_trip():
    """Test 4: Gallons to m^3 conversion and exact mathematical round trip."""
    vol_gal = 17.4e9  # 17.4 billion gallons
    vol_m3 = gallons_to_m3(vol_gal)

    assert vol_m3 == vol_gal * M3_PER_US_GALLON
    recovered_gal = m3_to_gallons(vol_m3)
    np.testing.assert_allclose(recovered_gal, vol_gal, rtol=1e-12)

    # Array input round-trip
    arr_gal = np.array([1.0, 100.0, 1e6, 211e9])
    arr_m3 = gallons_to_m3(arr_gal)
    arr_rec = m3_to_gallons(arr_m3)
    np.testing.assert_allclose(arr_rec, arr_gal, rtol=1e-12)


def test_zero_second_phase_growth_reproduces_previous_cost_curve():
    """The two-phase equation is exactly the original capped curve when g2 is zero."""
    rng = np.random.default_rng(7)
    w_dir, w_ind = rng.uniform(1.0, 20.0, (2, 8))
    g1, G1 = rng.uniform(0.0, 0.5, 8), rng.uniform(1.0, 20.0, 8)
    t = np.arange(1, 51)[np.newaxis, :]
    previous = calc_cost(w_dir[:, None], w_ind[:, None], 0.4, g1[:, None], G1[:, None], t)
    two_phase = calc_cost(
        w_dir[:, None], w_ind[:, None], 0.4, g1[:, None], G1[:, None], np.zeros((8, 1)), t
    )
    np.testing.assert_array_equal(two_phase, previous)


def test_pathway_benefits_never_exceed_ceilings_and_cost_ordering():
    """Test 3: Pathway benefits <= theoretical ceilings; direct-only cost <= direct+indirect."""
    rng = np.random.default_rng(42)
    n = 200
    t = np.arange(1, 51)[np.newaxis, :]

    # Solar food: Gross = phi * A * (1 - r) <= phi * A
    s = rng.choice([0.0, 1.0], size=(n, 1))
    alpha = rng.uniform(0.0, 1.0, size=(n, 1))
    phi = rng.uniform(0.0, 1.0, size=(n, 1))
    A = rng.uniform(1e11, 1e12, size=(n, 1))
    r = rng.uniform(0.0, 1.0, size=(n, 1))
    L = rng.uniform(0.0, 10.0, size=(n, 1))
    R = rng.uniform(0.0, 20.0, size=(n, 1))
    rho = rng.uniform(0.0, 0.5, size=(n, 1))

    b_sf = calc_benefit_solar_food(s, alpha, phi, A, r, L, R, rho, t)
    sf_ceiling = phi * A
    assert np.all(b_sf <= sf_ceiling + 1e-9)
    assert np.all(b_sf >= -1e-9)

    # Desal: Gross = D * theta
    D = rng.uniform(1e10, 5e10, size=(n, 1))
    theta = rng.uniform(0.0, 1.0, size=(n, 1))
    b_desal = calc_benefit_desal(s, alpha, D, theta, L, R, rho, t)
    desal_ceiling = D * theta
    assert np.all(b_desal <= desal_ceiling + 1e-9)
    assert np.all(b_desal >= -1e-9)

    # Cost ordering: direct-only (k=0) <= direct+electricity (k=1)
    w_dir = rng.uniform(1e9, 5e9, size=(n, 1))
    w_ind = rng.uniform(1e9, 5e9, size=(n, 1))
    g1 = rng.uniform(0.0, 0.3, size=(n, 1))
    G1 = rng.uniform(5.0, 15.0, size=(n, 1))
    g2 = rng.uniform(-0.1, 0.3, size=(n, 1))
    cost_k0 = calc_cost(w_dir, w_ind, 0.0, g1, G1, g2, t)
    cost_k1 = calc_cost(w_dir, w_ind, 1.0, g1, G1, g2, t)
    assert np.all(cost_k0 <= cost_k1)
