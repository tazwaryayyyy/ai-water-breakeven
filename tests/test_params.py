"""Tests for parameter validation, domain constraints, basis matching, and strict rejection."""

import pytest

from ai_water_breakeven.params import (
    Parameter,
    load_parameters,
    missing_rows_for_combination,
    select_scenario_parameters,
    validate_parameters,
)


@pytest.fixture
def base_params():
    return load_parameters("data/parameters.csv")


def test_validation_rejects_bad_ordering(base_params):
    """Test 7a: Low > high and triangular ordering violations are rejected."""
    # Triangular with mode < low
    bad_triang = dict(base_params)
    p = bad_triang["theta_desal"]
    bad_triang["theta_desal"] = Parameter(
        p.name,
        p.description,
        p.unit,
        p.basis,
        p.region,
        p.year,
        "triangular",
        low=0.20,
        mode=0.05,
        high=0.30,
        source=p.source,
        locator=p.locator,
        confidence=p.confidence,
        notes=p.notes,
    )
    with pytest.raises(ValueError, match="triangular requires low <= mode <= high"):
        validate_parameters(bad_triang)

    # Uniform with low > high
    bad_uniform = dict(base_params)
    p_u = bad_uniform["W_direct_global"]
    bad_uniform["W_direct_global"] = Parameter(
        p_u.name,
        p_u.description,
        p_u.unit,
        p_u.basis,
        p_u.region,
        p_u.year,
        "uniform",
        low=7.0e9,
        mode=5.0e9,
        high=4.0e9,
        source=p_u.source,
        locator=p_u.locator,
        confidence=p_u.confidence,
        notes=p_u.notes,
    )
    with pytest.raises(ValueError, match="low > high"):
        validate_parameters(bad_uniform)


def test_validation_rejects_illegal_negatives(base_params):
    """Test 7b: Illegal negative values for volume, probability, and lag are rejected."""
    # Negative water volume
    bad_vol = dict(base_params)
    p_v = bad_vol["W_direct_global"]
    bad_vol["W_direct_global"] = Parameter(
        p_v.name,
        p_v.description,
        p_v.unit,
        p_v.basis,
        p_v.region,
        p_v.year,
        p_v.distribution,
        low=-1.0,
        mode=0.0,
        high=10.0,
        source=p_v.source,
        locator=p_v.locator,
        confidence=p_v.confidence,
        notes=p_v.notes,
    )
    with pytest.raises(ValueError, match="invalid domain/sign"):
        validate_parameters(bad_vol)

    # Probability outside [0, 1]
    bad_prob = dict(base_params)
    p_p = bad_prob["p_desal"]
    bad_prob["p_desal"] = Parameter(
        p_p.name,
        p_p.description,
        p_p.unit,
        p_p.basis,
        p_p.region,
        p_p.year,
        p_p.distribution,
        low=0.5,
        mode=0.8,
        high=1.5,
        source=p_p.source,
        locator=p_p.locator,
        confidence=p_p.confidence,
        notes=p_p.notes,
    )
    with pytest.raises(ValueError, match="invalid domain/sign"):
        validate_parameters(bad_prob)


def test_validation_rejects_unknown_distributions(base_params):
    """Test 7c: Unsupported distribution names raise validation errors."""
    bad_dist = dict(base_params)
    p = bad_dist["p_desal"]
    bad_dist["p_desal"] = Parameter(
        p.name,
        p.description,
        p.unit,
        p.basis,
        p.region,
        p.year,
        "cauchy",
        low=0.1,
        mode=0.5,
        high=0.9,
        source=p.source,
        locator=p.locator,
        confidence=p.confidence,
        notes=p.notes,
    )
    with pytest.raises(ValueError, match="invalid distribution/basis"):
        validate_parameters(bad_dist)


def test_validation_basis_matching(base_params):
    """A selected scenario never combines a US cost set with global benefit rows."""
    with pytest.raises(ValueError, match="Basis mismatch:"):
        validate_parameters(base_params, cost_basis="us_consumption", allow_mixed_basis=False)

    missing = missing_rows_for_combination(base_params, "us", "consumption")
    assert missing == [
        "p_desal", "alpha_desal", "rho_desal", "L_desal", "R_desal", "D_desal",
        "theta_desal", "p_solar_food", "alpha_solar_food", "rho_solar_food",
        "L_solar_food", "R_solar_food", "phi_solar_food", "A_solar_food", "r_solar_food",
    ]


def test_basis_selection_uses_matching_or_na_rows(base_params):
    """Global consumption uses consumption rows and n/a rows, never withdrawal rows."""
    selected, missing = select_scenario_parameters(base_params, "global", "consumption")
    assert not missing
    assert selected["W_direct"].name == "W_direct_global_consumption"
    assert selected["A_solar_food"].name == "A_solar_food_consumption"
    assert selected["D_desal"].basis == "n/a"
    assert all(p.basis in {"consumption", "n/a"} for p in selected.values())


def test_validation_strict_mode_rejects_unverified_inputs(base_params):
    """Test 7e: Strict mode rejects any input marked MISSING or PLACEHOLDER."""
    with pytest.raises(ValueError, match="Strict rejection:"):
        validate_parameters(base_params, cost_basis="global_withdrawal", strict=True)
