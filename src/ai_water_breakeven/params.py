"""Parameter ingestion, unit conversion, and specification validation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from ai_water_breakeven.model import gallons_to_m3

VALID_DISTRIBUTIONS = {"fixed", "uniform", "triangular", "lognormal"}
VALID_BASES = {"withdrawal", "consumption", "n/a"}


@dataclass(frozen=True)
class Parameter:
    name: str
    description: str
    unit: str
    basis: str
    region: str
    year: int
    distribution: str
    low: float
    mode: float
    high: float
    source: str
    locator: str
    confidence: str
    notes: str

    @property
    def is_placeholder_or_missing(self) -> bool:
        src = self.source.strip().upper()
        return "PLACEHOLDER" in src or "MISSING" in src


def load_parameters(csv_path: str | Path) -> Dict[str, Parameter]:
    """Load parameter records from CSV and convert gallon volumes to cubic meters."""
    df = pd.read_csv(csv_path, skipinitialspace=True, keep_default_na=False)
    params: Dict[str, Parameter] = {}
    for _, r in df.iterrows():
        name, unit, basis = (
            str(r["name"]).strip(),
            str(r["unit"]).strip(),
            str(r["basis"]).strip().lower(),
        )
        if not basis or basis in ("", "na", "none"):
            basis = "n/a"
        low, mode, high = float(r["low"]), float(r["mode"]), float(r["high"])
        if unit in ("gal/yr", "gal"):
            low, mode, high, unit = (
                gallons_to_m3(low),
                gallons_to_m3(mode),
                gallons_to_m3(high),
                "m^3/yr",
            )
        params[name] = Parameter(
            name,
            str(r["description"]).strip(),
            unit,
            basis,
            str(r["region"]).strip(),
            int(r["year"]),
            str(r["distribution"]).strip().lower(),
            low,
            mode,
            high,
            str(r["source"]).strip(),
            str(r["locator"]).strip(),
            str(r["confidence"]).strip().upper(),
            str(r["notes"]).strip() if pd.notna(r["notes"]) else "",
        )
    return params


def validate_parameters(
    params: Dict[str, Parameter],
    cost_basis: str = "global_withdrawal",
    strict: bool = False,
    allow_mixed_basis: bool = False,
) -> Tuple[List[str], bool]:
    """Validate distribution names, ordering, signs, physical basis matching, and sources."""
    errors: List[str] = []
    for name, p in params.items():
        if p.distribution not in VALID_DISTRIBUTIONS or p.basis not in VALID_BASES:
            errors.append(f"'{name}': invalid distribution/basis")
        if p.distribution == "triangular" and not (p.low <= p.mode <= p.high):
            errors.append(f"'{name}': triangular requires low <= mode <= high")
        elif p.distribution in ("uniform", "lognormal") and p.low > p.high:
            errors.append(f"'{name}': low > high")
        if p.distribution == "lognormal" and p.low <= 0:
            errors.append(f"'{name}': lognormal low must be strictly positive")
        if (name.startswith(("W_", "D_", "A_", "L_", "R_", "rho_")) and p.low < 0) or (
            name.startswith(("p_", "alpha_")) and (p.low < 0 or p.high > 1)
        ):
            errors.append(f"'{name}': invalid domain/sign")

    cost_pfx = "us" if "us" in cost_basis.lower() else "global"
    c_bases = {
        params[c].basis
        for c in [f"W_direct_{cost_pfx}", f"W_indirect_{cost_pfx}"]
        if c in params and params[c].basis != "n/a"
    }
    b_bases = {
        params[b].basis
        for b in ["D_desal", "A_solar_food"]
        if b in params and params[b].basis != "n/a"
    }
    mixed = bool(c_bases and b_bases and c_bases != b_bases)
    if mixed and not allow_mixed_basis:
        errors.append(
            f"Basis mismatch: cost {c_bases} vs benefit {b_bases}. Pass --allow-mixed-basis."
        )

    if strict:
        for name, p in params.items():
            if p.is_placeholder_or_missing:
                errors.append(f"Strict rejection: '{name}' has unverified source '{p.source}'")

    if errors:
        raise ValueError("Parameter validation failed:\n  - " + "\n  - ".join(errors))
    return errors, mixed
