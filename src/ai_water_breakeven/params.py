"""Parameter ingestion, unit conversion, and specification validation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import warnings

import pandas as pd

from ai_water_breakeven.model import gallons_to_m3

VALID_DISTRIBUTIONS = {"fixed", "uniform", "triangular", "lognormal"}
VALID_BASES = {"withdrawal", "consumption", "n/a"}
VALID_REGIONS = {"global", "us"}

COST_ROLES = ("W_direct", "W_indirect", "g", "G")
BENEFIT_ROLES = (
    "p_desal",
    "alpha_desal",
    "rho_desal",
    "L_desal",
    "R_desal",
    "D_desal",
    "theta_desal",
    "p_solar_food",
    "alpha_solar_food",
    "rho_solar_food",
    "L_solar_food",
    "R_solar_food",
    "phi_solar_food",
    "A_solar_food",
    "r_solar_food",
)


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


def resolve_region_basis(
    region: str = "global", basis: str = "withdrawal", cost_basis: str | None = None
) -> tuple[str, str]:
    """Normalize independent scenario dimensions and map the deprecated combined value."""
    legacy = cost_basis or (region if "_" in region else None)
    if legacy:
        parts = legacy.lower().split("_", maxsplit=1)
        if len(parts) != 2 or parts[0] not in VALID_REGIONS or parts[1] not in VALID_BASES:
            raise ValueError(f"Invalid legacy cost_basis '{legacy}'")
        warnings.warn(
            "cost_basis is deprecated; use separate region and basis config keys.",
            UserWarning,
            stacklevel=2,
        )
        return parts[0], parts[1]
    return region.lower(), basis.lower()


def _role_candidates(role: str, region: str) -> tuple[str, ...]:
    """Return accepted CSV names for a role, including a future region-specific suffix."""
    if role in ("W_direct", "W_indirect", "g", "G"):
        return (f"{role}_{region}",)
    return (role, f"{role}_{region}")


def select_scenario_parameters(
    params: Dict[str, Parameter], region: str, basis: str
) -> tuple[Dict[str, Parameter], List[str]]:
    """Select only rows compatible with one region and one physical water basis."""
    selected: Dict[str, Parameter] = {}
    missing: List[str] = []
    for role in (*COST_ROLES, *BENEFIT_ROLES):
        names = _role_candidates(role, region)
        candidates = [
            p
            for name, p in params.items()
            if (name in names or name.startswith(f"{names[0]}_"))
            and p.region.lower() == region
            and p.basis in {basis, "n/a"}
        ]
        if len(candidates) == 1:
            selected[role] = candidates[0]
        elif not candidates:
            missing.append(role)
        else:
            missing.append(f"{role} (ambiguous matching rows)")
    return selected, missing


def missing_rows_for_combination(
    params: Dict[str, Parameter], region: str, basis: str
) -> List[str]:
    """List the required logical rows absent from a requested scenario combination."""
    _, missing = select_scenario_parameters(params, region, basis)
    return missing


def available_combinations(params: Dict[str, Parameter]) -> List[tuple[str, str]]:
    """Return cost-row region/basis combinations in deterministic order."""
    return sorted(
        {
            (p.region.lower(), p.basis)
            for name, p in params.items()
            if name.startswith("W_direct_") and p.basis != "n/a"
        }
    )


def validate_parameters(
    params: Dict[str, Parameter],
    region: str = "global",
    basis: str = "withdrawal",
    strict: bool = False,
    allow_mixed_basis: bool = False,
    *,
    cost_basis: str | None = None,
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

    region, basis = resolve_region_basis(region, basis, cost_basis)
    if region not in VALID_REGIONS or basis not in VALID_BASES - {"n/a"}:
        errors.append(f"Invalid scenario combination: region={region}, basis={basis}")
    else:
        _, missing = select_scenario_parameters(params, region, basis)
        if missing:
            errors.append(
                f"Basis mismatch: missing rows for region={region}, basis={basis}: {', '.join(missing)}"
            )

    if strict:
        for name, p in params.items():
            if p.is_placeholder_or_missing:
                errors.append(f"Strict rejection: '{name}' has unverified source '{p.source}'")

    if errors:
        raise ValueError("Parameter validation failed:\n  - " + "\n  - ".join(errors))
    # Mixed physical bases cannot be selected. This retained return value is false by construction.
    return errors, False
