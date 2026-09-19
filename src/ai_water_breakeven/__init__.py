"""AI water break-even Monte Carlo scenario model."""

from ai_water_breakeven.model import (
    M3_PER_US_GALLON,
    calc_benefit_desal,
    calc_benefit_solar_food,
    calc_cost,
    calc_net_balance,
    calc_ramp,
    find_annual_crossover,
    find_sustained_breakeven,
    gallons_to_m3,
    m3_to_gallons,
)

__all__ = [
    "M3_PER_US_GALLON",
    "calc_benefit_desal",
    "calc_benefit_solar_food",
    "calc_cost",
    "calc_net_balance",
    "calc_ramp",
    "find_annual_crossover",
    "find_sustained_breakeven",
    "gallons_to_m3",
    "m3_to_gallons",
]
__version__ = "0.1.0"
