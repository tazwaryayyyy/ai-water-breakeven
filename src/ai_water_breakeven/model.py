"""Pure array physical and balance calculations for water break-even."""

import numpy as np

M3_PER_US_GALLON: float = 0.003785411784


def gallons_to_m3(gallons: np.ndarray | float) -> np.ndarray | float:
    return gallons * M3_PER_US_GALLON


def m3_to_gallons(m3: np.ndarray | float) -> np.ndarray | float:
    return m3 / M3_PER_US_GALLON


def calc_cost(
    w_dir: np.ndarray,
    w_ind: np.ndarray,
    k: float,
    g1: np.ndarray,
    G1: np.ndarray,
    g2_or_t: np.ndarray,
    t: np.ndarray | None = None,
) -> np.ndarray:
    """Calculate a two-phase cost trajectory; omitted g2 retains the old curve exactly."""
    if t is None:
        t = g2_or_t
        g2 = np.zeros_like(g1)
    else:
        g2 = g2_or_t
    return (w_dir + k * w_ind) * ((1.0 + g1) ** np.minimum(t, G1)) * (
        (1.0 + g2) ** np.maximum(t - G1, 0)
    )


def calc_ramp(t: np.ndarray, lag: np.ndarray, ramp: np.ndarray) -> np.ndarray:
    # Step function if ramp duration is zero, else linear interpolation clipped to [0, 1]
    is_step = ramp == 0
    safe_r = np.where(is_step, 1.0, ramp)
    return np.where(is_step, np.where(t > lag, 1.0, 0.0), np.clip((t - lag) / safe_r, 0.0, 1.0))


def calc_benefit_desal(
    s: np.ndarray,
    alpha: np.ndarray,
    D: np.ndarray,
    theta: np.ndarray,
    lag: np.ndarray,
    ramp: np.ndarray,
    rho: np.ndarray,
    t: np.ndarray,
) -> np.ndarray:
    # Desalination supplies new water rather than reducing freshwater withdrawals
    return s * alpha * (D * theta) * calc_ramp(t, lag, ramp) * (1.0 - rho)


def calc_benefit_solar_food(
    s: np.ndarray,
    alpha: np.ndarray,
    phi: np.ndarray,
    A: np.ndarray,
    r: np.ndarray,
    lag: np.ndarray,
    ramp: np.ndarray,
    rho: np.ndarray,
    t: np.ndarray,
) -> np.ndarray:
    return s * alpha * (phi * A * (1.0 - r)) * calc_ramp(t, lag, ramp) * (1.0 - rho)


def calc_net_balance(total_benefit: np.ndarray, cost: np.ndarray) -> np.ndarray:
    return np.cumsum(total_benefit - cost, axis=-1)


def find_sustained_breakeven(net_balance: np.ndarray) -> np.ndarray:
    # Reverse cummin identifies earliest t where balance stays non-negative through horizon T
    rev_cummin = np.minimum.accumulate(net_balance[..., ::-1], axis=-1)[..., ::-1]
    is_sustained = rev_cummin >= 0.0
    first_idx = np.argmax(is_sustained, axis=-1)
    return np.where(np.any(is_sustained, axis=-1), (first_idx + 1).astype(float), np.nan)


def find_annual_crossover(total_benefit: np.ndarray, cost: np.ndarray) -> np.ndarray:
    crossover = total_benefit >= cost
    first_idx = np.argmax(crossover, axis=-1)
    return np.where(np.any(crossover, axis=-1), (first_idx + 1).astype(float), np.nan)
