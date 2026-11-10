"""Test helper functions for creating synthetic parameters."""

from ai_water_breakeven.params import Parameter


def make_param(name, unit, basis, region, dist, low, mode, high, source="S", confidence="C"):
    """Create a Parameter with minimal boilerplate."""
    return Parameter(
        name, "", unit, basis, region, 2027, dist, low, mode, high, source, "", confidence, ""
    )
