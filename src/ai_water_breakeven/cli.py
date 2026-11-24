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
    plot_knockout_probabilities,
    plot_net_balance_fan_chart,
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
from ai_water_breakeven.sample import create_scenario_rng, sample_parameter_matrix
from ai_water_breakeven.simulate import (
    KNOCKOUT_SCENARIOS,
    _apply_knockout,
    _copy_draws,
    _evaluate_samples,
    _knockout_row,
    compute_conditional_table,
    compute_conditions_table,
    compute_cost_trajectory,
    compute_net_balance_by_horizon,
    compute_prcc,
    compute_sourcing_priority,
    compute_summary_metrics,
    compute_threshold_map,
    compute_tornado,
    run_simulation,
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


def _git_tag() -> str | None:
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return out if out else None
    except Exception:
        return None


def _git_clean() -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
        ).stdout.strip()
        return len(out) == 0
    except Exception:
        return False


def _metadata(
    cfg: Dict[str, Any],
    p_path: Path,
    c_path: Path,
    res: Any | None = None,
    *,
    region: str = "global",
    basis: str = "withdrawal",
    n_samples: int | None = None,
    t_horizon: int | None = None,
    start_year: int | None = None,
    cost_scope: str | None = None,
    has_placeholder: bool | None = None,
    is_mixed_basis: bool | None = None,
    cli_args: list[str] | None = None,
    threshold_settings: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    n = n_samples if n_samples is not None else (res.n_samples if res else cfg.get("N", 100000))
    t = t_horizon if t_horizon is not None else (res.t_horizon if res else cfg.get("T", 50))
    yr = (
        start_year
        if start_year is not None
        else (getattr(res, "start_year", None) or cfg.get("start_year", 2027))
    )
    scope = (
        cost_scope
        if cost_scope is not None
        else (
            res.cost_scope
            if res
            else ("scope 1+2 combined" if region == "global" else "direct only")
        )
    )
    ph = has_placeholder if has_placeholder is not None else (res.has_placeholder if res else False)
    mix = is_mixed_basis if is_mixed_basis is not None else (res.is_mixed_basis if res else False)

    meta = {
        "git_commit": _git_commit(),
        "git_tag": _git_tag(),
        "working_tree_clean": _git_clean(),
        "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "software_version": ai_water_breakeven.__version__,
        "package_versions": {
            "ai_water_breakeven": ai_water_breakeven.__version__,
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "seed": cfg.get("seed", 42),
        "sample_count": n,
        "time_horizon": t,
        "baseline_year": yr,
        "region": region,
        "basis": basis,
        "cost_scope": scope,
        "sha256_parameters_csv": _file_sha256(p_path),
        "sha256_config_toml": _file_sha256(c_path),
        "placeholder_inputs_used": ph,
        "mixed_basis_used": mix,
        "publication_notice": PLACEHOLDER_NOTICE if ph else None,
        "cli_arguments": cli_args or sys.argv,
    }
    if threshold_settings is not None:
        meta["threshold_settings"] = threshold_settings
    return meta


def load_config(p: Path) -> Dict[str, Any]:
    if not p.is_file():
        return {}
    with open(p, "rb") as f:
        return tomllib.load(f)


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
    start_year = cfg.get("start_year", 2027)
    strict, allow_m = (
        args.strict or cfg.get("strict", False),
        args.allow_mixed_basis or cfg.get("allow_mixed_basis", False),
    )

    try:
        validate_parameters(
            params, region=region, basis=basis, strict=strict, allow_mixed_basis=allow_m
        )
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
        start_year=start_year,
    )

    summary = compute_summary_metrics(res)
    if res.has_placeholder:
        summary["publication_notice"] = PLACEHOLDER_NOTICE
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    _write_table(pd.DataFrame([summary]), out / "summary.csv", res.has_placeholder)
    _write_table(
        compute_prcc(res.sampled_params, res.final_net_balances),
        out / "prcc.csv",
        res.has_placeholder,
    )
    _write_table(
        compute_tornado(params, t_h, k_sw, region=region, basis=basis),
        out / "tornado.csv",
        res.has_placeholder,
    )
    _write_table(
        compute_conditions_table(res, cfg.get("conditions_horizon", 30), start_year=start_year),
        out / "conditions.csv",
        res.has_placeholder,
    )
    _write_table(
        compute_cost_trajectory(res, start_year=start_year),
        out / "cost_trajectory.csv",
        res.has_placeholder,
    )
    _write_table(
        compute_net_balance_by_horizon(res, start_year=start_year),
        out / "net_balance_by_horizon.csv",
        res.has_placeholder,
    )
    sourcing_df = compute_sourcing_priority(res)
    _write_table(sourcing_df, out / "sourcing_priority.csv", res.has_placeholder)
    conditional_df = compute_conditional_table(res)
    if res.basis_notice:
        conditional_df["basis_notice"] = res.basis_notice
    _write_table(conditional_df, out / "conditional.csv", res.has_placeholder)
    with open(out / "run_metadata.json", "w", encoding="utf-8") as f:
        json.dump(
            _metadata(
                cfg,
                Path(args.parameters),
                Path(args.config),
                res,
                region=region,
                basis=basis,
                start_year=start_year,
            ),
            f,
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
            f"{n_dominant} parameter(s) have |PRCC| > 0.85 ({names_str}) - "
            "check sourcing_priority.csv before treating results as more than illustrative."
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
    t_h, n_s = (
        getattr(args, "horizon", None) or cfg.get("T", 50),
        args.samples or cfg.get("N", 100000),
    )
    region, basis, seed = (*_scenario_dimensions(cfg, args), cfg.get("seed", 42))
    start_year = cfg.get("start_year", 2027)
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

    r0 = run_simulation(
        params,
        t_h,
        n_s,
        0.0,
        seed=seed,
        scenario_idx=0,
        allow_mixed_basis=allow_m,
        region=region,
        basis=basis,
        start_year=start_year,
    )
    r1 = (
        None
        if region == "global"
        else run_simulation(
            params,
            t_h,
            n_s,
            1.0,
            seed=seed,
            scenario_idx=1,
            allow_mixed_basis=allow_m,
            region=region,
            basis=basis,
            start_year=start_year,
        )
    )

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
    plot_breakeven_distribution(
        r0,
        out / "fig8_breakeven_given_solar_food",
        mask=r0.deployments["s_solar_food"] == 1,
        label="given solar-food deployment",
    )
    with open(out / "run_metadata.json", "w", encoding="utf-8") as f:
        json.dump(
            _metadata(
                cfg,
                Path(args.parameters),
                Path(args.config),
                r0,
                region=region,
                basis=basis,
                start_year=start_year,
            ),
            f,
            indent=2,
        )
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
    start_year = cfg.get("start_year", 2027)
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
    active, missing = select_scenario_parameters(params, region, basis)
    if missing:
        raise ValueError(f"Missing rows for region={region}, basis={basis}: {', '.join(missing)}")
    base_samples, base_deployments = sample_parameter_matrix(
        list(active.values()), n_s, create_scenario_rng(cfg.get("seed", 42), 0)
    )
    k_sw = cfg.get("k", 0.0)
    rows = []
    baseline_summary: Dict[str, Any] = {}
    baseline_meta: Dict[str, Any] = {}
    for name in KNOCKOUT_SCENARIOS:
        samples, deployments = _copy_draws(base_samples, base_deployments)
        _apply_knockout(name, samples, deployments, active)
        result = _evaluate_samples(
            active, samples, deployments, t_h, k_sw, region, basis, start_year=start_year
        )
        summary = compute_summary_metrics(result)
        if name == "baseline":
            baseline_summary = summary
            baseline_meta = {
                "has_placeholder": result.has_placeholder,
                "cost_scope": result.cost_scope,
                "basis_notice": result.basis_notice,
            }
        rows.append(
            _knockout_row(
                name, summary, baseline_summary, result.t_horizon, baseline_meta["basis_notice"]
            )
        )
    table = pd.DataFrame(rows)
    _write_table(table, out / "knockouts.csv", baseline_meta["has_placeholder"])
    plot_knockout_probabilities(
        table,
        out / "fig6_knockouts",
        baseline_meta["has_placeholder"],
        cost_scope=baseline_meta["cost_scope"],
        basis_notice=baseline_meta["basis_notice"],
    )
    with open(out / "run_metadata.json", "w", encoding="utf-8") as f:
        json.dump(
            _metadata(
                cfg,
                Path(args.parameters),
                Path(args.config),
                region=region,
                basis=basis,
                n_samples=n_s,
                t_horizon=t_h,
                start_year=start_year,
                cost_scope=baseline_meta["cost_scope"],
                has_placeholder=baseline_meta["has_placeholder"],
            ),
            f,
            indent=2,
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

    model_horizon = cfg.get("T", 50)
    x_name = getattr(args, "x", None) or "g_global"
    y_name = getattr(args, "y", None) or "phi_solar_food"
    h_arg = getattr(args, "horizon", None)
    horizon = cfg.get("conditions_horizon", 30) if h_arg is None else h_arg
    eh_arg = getattr(args, "eval_horizon", None)
    eval_horizon = model_horizon if eh_arg is None else eh_arg
    grid = getattr(args, "grid", None) or 15
    n_per_cell = getattr(args, "n_per_cell", None) or 5000
    start_year = cfg.get("start_year", 2027)

    if horizon <= 0:
        print(f"Validation error: Reporting horizon ({horizon}) must be positive.", file=sys.stderr)
        return 1
    if eval_horizon <= 0:
        print(
            f"Validation error: Evaluation horizon ({eval_horizon}) must be positive.",
            file=sys.stderr,
        )
        return 1
    if eval_horizon < horizon:
        print(
            f"Validation error: Evaluation horizon ({eval_horizon}) must be at least "
            f"reporting horizon ({horizon}).",
            file=sys.stderr,
        )
        return 1
    if horizon > model_horizon:
        print(
            f"Validation error: Reporting horizon ({horizon}) cannot exceed "
            f"configured model horizon ({model_horizon}).",
            file=sys.stderr,
        )
        return 1
    if eval_horizon > model_horizon:
        print(
            f"Validation error: Evaluation horizon ({eval_horizon}) cannot exceed "
            f"configured model horizon ({model_horizon}).",
            file=sys.stderr,
        )
        return 1

    x_range = getattr(args, "x_range", None)
    y_range = getattr(args, "y_range", None)
    log_spacing = getattr(args, "log", False)
    conditional = getattr(args, "conditional", "none")
    conditional = None if conditional in (None, "none") else conditional

    try:
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
            x_range=x_range,
            y_range=y_range,
            log_spacing=log_spacing,
            conditional=conditional,
            eval_horizon=eval_horizon,
        )
    except ValueError as e:
        print(f"Threshold computation error:\n{e}", file=sys.stderr)
        return 1

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
            "desal benefit is identically zero under this parameter set "
            "(for example, unset sentinel inputs) - results reflect the remaining pathways only."
        )
    if float(gross_sf_max) == 0.0:
        thresh_notices.append(
            "solar_food benefit is identically zero under this parameter set "
            "(for example, unset sentinel inputs) - results reflect the remaining pathways only."
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
        log_spacing=log_spacing,
    )
    threshold_meta = {
        "x": x_name,
        "y": y_name,
        "reporting_horizon": horizon,
        "evaluation_horizon": eval_horizon,
        "grid": grid,
        "n_per_cell": n_per_cell,
        "x_range": x_range,
        "y_range": y_range,
        "log_spacing": log_spacing,
        "conditional": conditional,
    }
    with open(out / "run_metadata.json", "w", encoding="utf-8") as f:
        json.dump(
            _metadata(
                cfg,
                Path(args.parameters),
                Path(args.config),
                region=region,
                basis=basis,
                n_samples=grid * grid * n_per_cell,
                t_horizon=eval_horizon,
                start_year=start_year,
                cost_scope=cost_scope,
                has_placeholder=has_placeholder,
                threshold_settings=threshold_meta,
            ),
            f,
            indent=2,
        )
    print(f"Threshold map written to {out}")
    return 0


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Regenerate every output for each complete cost region/basis combination."""
    cfg, params, root = (
        load_config(Path(args.config)),
        load_parameters(args.parameters),
        Path(args.out_dir),
    )
    root.mkdir(parents=True, exist_ok=True)
    preferred = _scenario_dimensions(cfg, args)
    combinations = available_combinations(params)
    ordered = [preferred] + [item for item in combinations if item != preferred]
    status_rows, ran, skipped = [], [], []

    # Threshold settings exposed through reproduce
    th_x = getattr(args, "threshold_x", None) or getattr(args, "x", None) or "g_global"
    th_y = getattr(args, "threshold_y", None) or getattr(args, "y", None) or "phi_solar_food"
    th_grid = getattr(args, "threshold_grid", None) or getattr(args, "grid", None) or 15
    th_n = getattr(args, "threshold_n_per_cell", None) or getattr(args, "n_per_cell", None) or 5000
    th_xr = getattr(args, "threshold_x_range", None) or getattr(args, "x_range", None)
    th_yr = getattr(args, "threshold_y_range", None) or getattr(args, "y_range", None)
    th_log = getattr(args, "threshold_log", False) or getattr(args, "log", False)
    th_cond = getattr(args, "threshold_conditional", None) or getattr(args, "conditional", "none")

    for region, basis in ordered:
        missing = missing_rows_for_combination(params, region, basis)
        if missing:
            record = {
                "region": region,
                "basis": basis,
                "status": "skipped",
                "missing_rows": ", ".join(missing),
            }
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
        t_h = local.horizon or cfg.get("T", 50)

        # Threshold reporting horizon defaults to conditions_horizon capped by t_h
        th_rep_h = getattr(args, "threshold_horizon", None)
        if th_rep_h is None:
            th_rep_h = min(cfg.get("conditions_horizon", 30), t_h)
        else:
            th_rep_h = min(th_rep_h, t_h)

        # Threshold evaluation horizon defaults to configured model horizon t_h
        th_eval_h = (
            getattr(args, "threshold_eval_horizon", None)
            or getattr(args, "eval_horizon", None)
            or t_h
        )

        threshold_args = argparse.Namespace(**vars(local))
        threshold_args.x = th_x
        threshold_args.y = th_y
        threshold_args.horizon = th_rep_h
        threshold_args.eval_horizon = th_eval_h
        threshold_args.grid = th_grid
        threshold_args.n_per_cell = th_n
        threshold_args.x_range = th_xr
        threshold_args.y_range = th_yr
        threshold_args.log = th_log
        threshold_args.conditional = th_cond

        for command in (cmd_run, cmd_figures, cmd_knockouts):
            if command(local) != 0:
                return 1
        if cmd_threshold(threshold_args) != 0:
            return 1
        record = {"region": region, "basis": basis, "status": "ran", "missing_rows": ""}
        status_rows.append(record)
        ran.append({"region": region, "basis": basis, "out_dir": local.out_dir})
    has_placeholder = any(p.is_placeholder_or_missing for p in params.values())
    _write_table(pd.DataFrame(status_rows), root / "reproduce_status.csv", has_placeholder)
    reproduce_manifest = {
        "ran": ran,
        "skipped": skipped,
        "publication_notice": PLACEHOLDER_NOTICE if has_placeholder else None,
        "metadata": _metadata(
            cfg,
            Path(args.parameters),
            Path(args.config),
            region=preferred[0],
            basis=preferred[1],
            n_samples=args.samples or cfg.get("N", 100000),
            t_horizon=args.horizon or cfg.get("T", 50),
            start_year=cfg.get("start_year", 2027),
            has_placeholder=has_placeholder,
        ),
    }
    with open(root / "reproduce_manifest.json", "w", encoding="utf-8") as f:
        json.dump(reproduce_manifest, f, indent=2)
    print(f"Reproduction complete. Skipped combinations: {len(skipped)}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        prog="ai-water-breakeven", description="Monte Carlo break-even model"
    )
    sub = p.add_subparsers(dest="command", required=True)
    for name in ["validate", "run", "figures", "knockouts", "threshold", "reproduce"]:
        sp = sub.add_parser(name)
        sp.add_argument("--parameters", default="data/parameters.csv")
        sp.add_argument("--config", default="configs/base.toml")
        sp.add_argument("--strict", action="store_true")
        sp.add_argument("--allow-mixed-basis", action="store_true")
        sp.add_argument("--region", choices=["global", "us"], default=None)
        sp.add_argument("--basis", choices=["withdrawal", "consumption"], default=None)
        if name in ("run", "figures", "knockouts", "reproduce"):
            sp.add_argument("--out-dir", default="results")
            sp.add_argument("--samples", type=int, default=None)
            sp.add_argument("--horizon", type=int, default=None)
        elif name == "threshold":
            sp.add_argument("--out-dir", default="results")
            sp.add_argument("--x", default="g_global")
            sp.add_argument("--y", default="phi_solar_food")
            sp.add_argument("--horizon", type=int, default=30)
            sp.add_argument("--eval-horizon", dest="eval_horizon", type=int, default=None)
            sp.add_argument("--grid", type=int, default=15)
            sp.add_argument("--n-per-cell", dest="n_per_cell", type=int, default=5000)
            sp.add_argument("--x-range", nargs=2, type=float, default=None, metavar=("LO", "HI"))
            sp.add_argument("--y-range", nargs=2, type=float, default=None, metavar=("LO", "HI"))
            sp.add_argument("--log", action="store_true")
            sp.add_argument(
                "--conditional", choices=["none", "solar_food", "desal", "both"], default="none"
            )
        if name == "reproduce":
            sp.add_argument("--threshold-x", "--x", dest="threshold_x", default=None)
            sp.add_argument("--threshold-y", "--y", dest="threshold_y", default=None)
            sp.add_argument("--threshold-horizon", type=int, default=None)
            sp.add_argument(
                "--threshold-eval-horizon",
                "--eval-horizon",
                dest="threshold_eval_horizon",
                type=int,
                default=None,
            )
            sp.add_argument(
                "--threshold-grid", "--grid", dest="threshold_grid", type=int, default=None
            )
            sp.add_argument(
                "--threshold-n-per-cell",
                "--n-per-cell",
                dest="threshold_n_per_cell",
                type=int,
                default=None,
            )
            sp.add_argument(
                "--threshold-x-range",
                "--x-range",
                dest="threshold_x_range",
                nargs=2,
                type=float,
                default=None,
                metavar=("LO", "HI"),
            )
            sp.add_argument(
                "--threshold-y-range",
                "--y-range",
                dest="threshold_y_range",
                nargs=2,
                type=float,
                default=None,
                metavar=("LO", "HI"),
            )
            sp.add_argument("--threshold-log", "--log", dest="threshold_log", action="store_true")
            sp.add_argument(
                "--threshold-conditional",
                "--conditional",
                dest="threshold_conditional",
                choices=["none", "solar_food", "desal", "both"],
                default=None,
            )

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
