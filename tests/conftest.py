"""Shared fixtures for the test suite."""

import pytest

from ai_water_breakeven.params import Parameter

_SYNTHETIC_SPECS = {
    "W_direct_global": ("m^3/yr", "withdrawal", "fixed", 5.0e9, 5.0e9, 5.0e9),
    "W_indirect_global": ("m^3/yr", "withdrawal", "fixed", 0.0, 0.0, 0.0),
    "g_global": ("dimensionless", "n/a", "triangular", 0.10, 0.20, 0.30),
    "G_global": ("yr", "n/a", "fixed", 5.0, 5.0, 5.0),
    "g2_global": ("dimensionless", "n/a", "fixed", 0.0, 0.0, 0.0),
    "p_desal": ("dimensionless", "n/a", "fixed", 0.8, 0.8, 0.8),
    "alpha_desal": ("dimensionless", "n/a", "fixed", 0.15, 0.15, 0.15),
    "rho_desal": ("dimensionless", "n/a", "fixed", 0.10, 0.10, 0.10),
    "L_desal": ("yr", "n/a", "fixed", 5.0, 5.0, 5.0),
    "R_desal": ("yr", "n/a", "fixed", 10.0, 10.0, 10.0),
    "D_desal": ("m^3/yr", "n/a", "fixed", 3.5e10, 3.5e10, 3.5e10),
    "theta_desal": ("dimensionless", "n/a", "fixed", 0.05, 0.05, 0.05),
    "p_solar_food": ("dimensionless", "n/a", "fixed", 0.5, 0.5, 0.5),
    "alpha_solar_food": ("dimensionless", "n/a", "fixed", 0.25, 0.25, 0.25),
    "rho_solar_food": ("dimensionless", "n/a", "fixed", 0.10, 0.10, 0.10),
    "L_solar_food": ("yr", "n/a", "fixed", 5.0, 5.0, 5.0),
    "R_solar_food": ("yr", "n/a", "fixed", 10.0, 10.0, 10.0),
    "phi_solar_food": ("dimensionless", "n/a", "triangular", 0.01, 0.03, 0.06),
    "A_solar_food": ("m^3/yr", "withdrawal", "fixed", 2.8e12, 2.8e12, 2.8e12),
    "r_solar_food": ("dimensionless", "withdrawal", "fixed", 0.20, 0.20, 0.20),
}


@pytest.fixture
def synthetic_params():
    """Build the shared synthetic parameter set with (distribution, low, mode, high) overrides."""

    def build(overrides=None):
        specs = dict(_SYNTHETIC_SPECS)
        for name, (dist, low, mode, high) in (overrides or {}).items():
            unit, basis = specs[name][:2]
            specs[name] = (unit, basis, dist, low, mode, high)
        return {
            name: Parameter(
                name, "", unit, basis, "global", 2027, dist, low, mode, high, "S", "", "C", ""
            )
            for name, (unit, basis, dist, low, mode, high) in specs.items()
        }

    return build
