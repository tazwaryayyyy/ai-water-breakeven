"""Command-line interface with subcommands: validate, run, figures, reproduce."""

import argparse
import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict

import matplotlib
import numpy as np
import pandas as pd
import scipy

import ai_water_breakeven
from ai_water_breakeven.figures import (
    plot_breakeven_distribution,
    plot_net_balance_fan_chart,
    plot_knockout_probabilities,
    plot_probability_vs_horizon,
    plot_scope_comparison,
    plot_threshold_map,
    plot_tornado_chart,
)
from ai_water_breakeven.params import (
    available_combinations,
    load_parameters,
    missing_rows_for_combination,
    resolve_region_basis,
    select_scenario_parameters,
    validate_parameters,
)
from ai_water_breakeven.simulate import (
    compute_conditions_table,
    compute_cost_trajectory,
    compute_knockout_table,
    compute_net_balance_by_horizon,
    compute_prcc,
    compute_summary_metrics,
    compute_sourcing_priority,
    compute_tornado,
    compute_threshold_map,
    run_simulation,
    run_knockout_scenarios,
)

PLACEHOLDER_NOTICE = "PLACEHOLDER INPUTS - NOT FOR PUBLICATION"


def _write_table(df: pd.DataFrame, path: Path, has_placeholder: bool) -> None:
    """Keep the publication warning visible in every table from unverified inputs."""
    table = df.copy()
    if has_placeholder:
        table["publication_notice"] = PLACEHOLDER_NOTICE
    table.to_csv(path, index=False)


def _file_sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "missing"


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown_or_uncommitted"


def _metadata(cfg: Dict[str, Any], p_path: Path, c_path: Path, res: Any) -> Dict[str, Any]:
    return {
        "git_commit": _git_commit(),
        "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "package_versions": {
            "ai_water_breakeven": ai_water_breakeven.__version__,
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "seed": cfg.get("seed", 42),
        "sha256_parameters_csv": _file_sha256(p_path),
        "sha256_config_toml": _file_sha256(c_path),
        "placeholder_inputs_used": res.has_placeholder,
        "mixed_basis_used": res.is_mixed_basis,
        "cost_scope": res.cost_scope,
        "publication_notice": PLACEHOLDER_NOTICE if res.has_placeholder else None,
    }


def load_config(p: Path) -> Dict[str, Any]:
    return tomllib.load(open(p, "rb")) if p.is_file() else {}


def _scenario_dimensions(cfg: Dict[str, Any], args: argparse.Namespace) -> tuple[str, str]:
    """Read independent scenario dimensions, including a deprecated combined config value."""
    return resolve_region_basis(
        getattr(args, "region", None) or cfg.get("region", "global"),
        getattr(args, "basis", None) or cfg.get("basis", "withdrawal"),
        cfg.get("cost_basis"),
    )


def cmd_validate(args: argparse.Namespace) -> int:
    cfg, params = load_config(Path(args.config)), load_parameters(args.parameters)
    try:
        region, basis = _scenario_dimensions(cfg, args)
        validate_parameters(
            params,
            region=region,
            basis=basis,
            strict=args.strict or cfg.get("strict", False),
            allow_mixed_basis=args.allow_mixed_basis or cfg.get("allow_mixed_basis", False),
        )
        print("Validation passed.")
        return 0
    except ValueError as e:
        print(f"Validation failed:\n{e}", file=sys.stderr)
        return 1


def cmd_run(args: argparse.Namespace) -> int:
    cfg, params, out = (
        load_config(Path(args.config)),
        load_parameters(args.parameters),
        Path(args.out_dir),
    )
    out.mkdir(parents=True, exist_ok=True)
    t_h, n_s = args.horizon or cfg.get("T", 50), args.samples or cfg.get("N", 100000)
    region, basis = _scenario_dimensions(cfg, args)
    k_sw = cfg.get("k", 0.0)
    strict, allow_m = (
        args.strict or cfg.get("strict", False),
        args.allow_mixed_basis or cfg.get("allow_mixed_basis", False),
    )

    try:
        validate_parameters(params, region=region, basis=basis, strict=strict, allow_mixed_basis=allow_m)
    except ValueError as e:
        print(f"Validation failed:\n{e}", file=sys.stderr)
        return 1
    res = run_simulation(
        params,
        t_h,
        n_s,
        k_sw,
        seed=cfg.get("seed", 42),
        allow_mixed_basis=allow_m,
        region=region,
        basis=basis,
    )

    summary = compute_summary_metrics(res)
    if res.has_placeholder:
        summary["publication_notice"] = PLACEHOLDER_NOTICE
    json.dump(summary, open(out / "summary.json", "w", encoding="utf-8"), indent=2)
    _write_table(pd.DataFrame([summary]), out / "summary.csv", res.has_placeholder)
    _write_table(
        compute_prcc(res.sampled_params, res.final_net_balances), out / "prcc.csv", res.has_placeholder
    )
    _write_table(
        compute_tornado(params, t_h, k_sw, region=region, basis=basis),
        out / "tornado.csv",
        res.has_placeholder,
    )
    _write_table(
        compute_conditions_table(res, cfg.get("conditions_horizon", 30)),
        out / "conditions.csv",
        res.has_placeholder,
    )
    _write_table(compute_cost_trajectory(res), out / "cost_trajectory.csv", res.has_placeholder)
    _write_table(
        compute_net_balance_by_horizon(res), out / "net_balance_by_horizon.csv", res.has_placeholder
    )
    sourcing_df = compute_sourcing_priority(res)
    _write_table(sourcing_df, out / "sourcing_priority.csv", res.has_placeholder)
    json.dump(
        _metadata(cfg, Path(args.parameters), Path(args.config), res),
        open(out / "run_metadata.json", "w", encoding="utf-8"),
        indent=2,
    )
    dominant_params = (
        sourcing_df.loc[sourcing_df["dominance_warning"], "parameter"].tolist()
        if "dominance_warning" in sourcing_df
        else []
    )
    n_dominant = len(dominant_params)
    if n_dominant > 0:
        names_str = ", ".join(dominant_params)
        print(
            f"{n_dominant} parameter(s) have |PRCC| > 0.85 ({names_str}) - check sourcing_priority.csv before treating results as more than illustrative."
        )
    print(f"Run complete. Outputs in {out}")
    return 0


def cmd_figures(args: argparse.Namespace) -> int:
    cfg, params, out = (
        load_config(Path(args.config)),
        load_parameters(args.parameters),
        Path(args.out_dir),
    )
    out.mkdir(parents=True, exist_ok=True)
    t_h, n_s = cfg.get("T", 50), args.samples or cfg.get("N", 100000)
    region, basis, seed = (*_scenario_dimensions(cfg, args), cfg.get("seed", 42))
    allow_m = args.allow_mixed_basis or cfg.get("allow_mixed_basis", False)

    try:
        validate_parameters(
            params,
            region=region,
            basis=basis,
            strict=args.strict or cfg.get("strict", False),
            allow_mixed_basis=allow_m,
        )
    except ValueError as e:
        print(f"Validation failed:\n{e}", file=sys.stderr)
        return 1

    r0 = run_simulation(params, t_h, n_s, 0.0, seed=seed, scenario_idx=0, allow_mixed_basis=allow_m, region=region, basis=basis)
    r1 = run_simulation(params, t_h, n_s, 1.0, seed=seed, scenario_idx=1, allow_mixed_basis=allow_m, region=region, basis=basis)

    plot_breakeven_distribution(r0, out / "fig1_breakeven_dist")
    plot_probability_vs_horizon(r0, out / "fig2_p_breakeven_horizon")
    plot_net_balance_fan_chart(r0, out / "fig3_net_balance_fan")
    plot_tornado_chart(
        compute_tornado(params, t_h, 0.0, region=region, basis=basis),
        out / "fig4_tornado",
        r0.has_placeholder,
        r0.is_mixed_basis,
        cost_scope=r0.cost_scope,
        basis_notice=r0.basis_notice,
    )
    plot_scope_comparison(r0, r1, out / "fig5_scope_comparison")
    print(f"Figures written to {out}")
    return 0


def cmd_knockouts(args: argparse.Namespace) -> int:
    """Write scenario knockouts based on one shared sampled matrix."""
    cfg, params, out = (
        load_config(Path(args.config)),
        load_parameters(args.parameters),
        Path(args.out_dir),
    )
    out.mkdir(parents=True, exist_ok=True)
    region, basis = _scenario_dimensions(cfg, args)
    t_h, n_s = args.horizon or cfg.get("T", 50), args.samples or cfg.get("N", 100000)
    try:
        validate_parameters(
            params,
            region=region,
            basis=basis,
            strict=args.strict or cfg.get("strict", False),
            allow_mixed_basis=args.allow_mixed_basis or cfg.get("allow_mixed_basis", False),
        )
    except ValueError as e:
        print(f"Validation failed:\n{e}", file=sys.stderr)
        return 1
    results = run_knockout_scenarios(
        params,
        t_h,
        n_s,
        cfg.get("k", 0.0),
        cfg.get("seed", 42),
        region,
        basis,
    )
    table = compute_knockout_table(results)
    _write_table(table, out / "knockouts.csv", results["baseline"].has_placeholder)
    plot_knockout_probabilities(
        table,
        out / "fig6_knockouts",
        results["baseline"].has_placeholder,
        cost_scope=results["baseline"].cost_scope,
        basis_notice=results["baseline"].basis_notice,
    )
    print(f"Knockout outputs written to {out}")
    return 0


def cmd_threshold(args: argparse.Namespace) -> int:
    """Write a two-parameter threshold map for the configured scenario dimensions."""
    cfg, params, out = (
        load_config(Path(args.config)),
        load_parameters(args.parameters),
        Path(args.out_dir),
    )
    out.mkdir(parents=True, exist_ok=True)
    region, basis = _scenario_dimensions(cfg, args)
    try:
        validate_parameters(
            params,
            region=region,
            basis=basis,
            strict=args.strict or cfg.get("strict", False),
            allow_mixed_basis=args.allow_mixed_basis or cfg.get("allow_mixed_basis", False),
        )
    except ValueError as e:
        print(f"Validation failed:\n{e}", file=sys.stderr)
        return 1
    x_name, y_name = getattr(args, "x", "g_global"), getattr(args, "y", "phi_solar_food")
    horizon = getattr(args, "horizon", None) or cfg.get("conditions_horizon", 30)
    grid, n_per_cell = getattr(args, "grid", 15), getattr(args, "n_per_cell", 5000)
    table = compute_threshold_map(
        params,
        x_name,
        y_name,
        horizon,
        grid,
        n_per_cell,
        cfg.get("seed", 42),
        cfg.get("k", 0.0),
        region,
        basis,
    )
    active, _ = select_scenario_parameters(params, region, basis)
    by_name = {param.name: param for param in active.values()}
    has_placeholder = any(param.is_placeholder_or_missing for param in active.values())
    cost_scope = "scope 1+2 combined" if region == "global" else None

    gross_d_max = active["D_desal"].high * active["theta_desal"].high
    gross_sf_max = (
        active["phi_solar_food"].high
        * active["A_solar_food"].high
        * max(0.0, 1.0 - active["r_solar_food"].low)
    )
    thresh_notices = []
    if float(gross_d_max) == 0.0:
        thresh_notices.append(
            "desal benefit is identically zero under this parameter set (for example, unset sentinel inputs) - results reflect the remaining pathways only."
        )
    if float(gross_sf_max) == 0.0:
        thresh_notices.append(
            "solar_food benefit is identically zero under this parameter set (for example, unset sentinel inputs) - results reflect the remaining pathways only."
        )
    thresh_notice = "; ".join(thresh_notices) if thresh_notices else None

    _write_table(table, out / "threshold_map.csv", has_placeholder)
    plot_threshold_map(
        table,
        out / "fig7_threshold_map",
        f"{x_name} ({by_name[x_name].unit})",
        f"{y_name} ({by_name[y_name].unit})",
        has_placeholder,
        cost_scope=cost_scope,
        basis_notice=thresh_notice,
    )
    print(f"Threshold map written to {out}")
    return 0


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Regenerate every output for each complete cost region/basis combination."""
    cfg, params, root = load_config(Path(args.config)), load_parameters(args.parameters), Path(args.out_dir)
    root.mkdir(parents=True, exist_ok=True)
    preferred = _scenario_dimensions(cfg, args)
    combinations = available_combinations(params)
    ordered = [preferred] + [item for item in combinations if item != preferred]
    status_rows, ran, skipped = [], [], []
    for region, basis in ordered:
        missing = missing_rows_for_combination(params, region, basis)
        if missing:
            record = {"region": region, "basis": basis, "status": "skipped", "missing_rows": ", ".join(missing)}
            status_rows.append(record)
            skipped.append(record)
            continue
        local = argparse.Namespace(**vars(args))
        local.region, local.basis = region, basis
        local.out_dir = str(root if (region, basis) == preferred else root / f"{region}_{basis}")
        try:
            validate_parameters(
                params,
                region=region,
                basis=basis,
                strict=local.strict or cfg.get("strict", False),
                allow_mixed_basis=local.allow_mixed_basis or cfg.get("allow_mixed_basis", False),
            )
        except ValueError as error:
            print(f"Validation failed:\n{error}", file=sys.stderr)
            return 1
        for command in (cmd_run, cmd_figures, cmd_knockouts, cmd_threshold):
            if command(local) != 0:
                return 1
        record = {"region": region, "basis": basis, "status": "ran", "missing_rows": ""}
        status_rows.append(record)
        ran.append({"region": region, "basis": basis, "out_dir": local.out_dir})
    has_placeholder = any(p.is_placeholder_or_missing for p in params.values())
    _write_table(pd.DataFrame(status_rows), root / "reproduce_status.csv", has_placeholder)
    json.dump(
        {
            "ran": ran,
            "skipped": skipped,
            "publication_notice": PLACEHOLDER_NOTICE if has_placeholder else None,
        },
        open(root / "reproduce_manifest.json", "w", encoding="utf-8"),
        indent=2,
    )
    print(f"Reproduction complete. Skipped combinations: {len(skipped)}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        prog="ai-water-breakeven", description="Monte Carlo break-even model"
    )
    sub = p.add_subparsers(dest="command", required=True)
    for name, fn in [
        ("validate", cmd_validate),
        ("run", cmd_run),
        ("figures", cmd_figures),
        ("knockouts", cmd_knockouts),
        ("threshold", cmd_threshold),
        ("reproduce", cmd_reproduce),
    ]:
        sp = sub.add_parser(name)
        sp.add_argument("--parameters", default="data/parameters.csv")
        sp.add_argument("--config", default="configs/base.toml")
        sp.add_argument("--strict", action="store_true")
        sp.add_argument("--allow-mixed-basis", action="store_true")
        sp.add_argument("--region", choices=["global", "us"], default=None)
        sp.add_argument("--basis", choices=["withdrawal", "consumption"], default=None)
        if name in ("run", "figures", "knockouts", "threshold", "reproduce"):
            sp.add_argument("--out-dir", default="results")
            sp.add_argument("--samples", type=int, default=None)
        if name in ("run", "knockouts", "reproduce"):
            sp.add_argument("--horizon", type=int, default=None)
        if name == "threshold":
            sp.add_argument("--x", default="g_global")
            sp.add_argument("--y", default="phi_solar_food")
            sp.add_argument("--horizon", type=int, default=30)
            sp.add_argument("--grid", type=int, default=15)
            sp.add_argument("--n-per-cell", dest="n_per_cell", type=int, default=5000)

    args = p.parse_args()
    cmds = {
        "validate": cmd_validate,
        "run": cmd_run,
        "figures": cmd_figures,
        "knockouts": cmd_knockouts,
        "threshold": cmd_threshold,
        "reproduce": cmd_reproduce,
    }
    sys.exit(cmds[args.command](args))


if __name__ == "__main__":
    main()
