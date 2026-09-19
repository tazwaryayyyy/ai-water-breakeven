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
    plot_probability_vs_horizon,
    plot_scope_comparison,
    plot_tornado_chart,
)
from ai_water_breakeven.params import load_parameters, validate_parameters
from ai_water_breakeven.simulate import (
    compute_conditions_table,
    compute_prcc,
    compute_summary_metrics,
    compute_tornado,
    run_simulation,
)


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
    }


def load_config(p: Path) -> Dict[str, Any]:
    return tomllib.load(open(p, "rb")) if p.is_file() else {}


def cmd_validate(args: argparse.Namespace) -> int:
    cfg, params = load_config(Path(args.config)), load_parameters(args.parameters)
    try:
        validate_parameters(
            params,
            cfg.get("cost_basis", "global_withdrawal"),
            args.strict or cfg.get("strict", False),
            args.allow_mixed_basis or cfg.get("allow_mixed_basis", False),
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
    c_basis, k_sw = cfg.get("cost_basis", "global_withdrawal"), cfg.get("k", 0.0)
    strict, allow_m = (
        args.strict or cfg.get("strict", False),
        args.allow_mixed_basis or cfg.get("allow_mixed_basis", False),
    )

    validate_parameters(params, c_basis, strict, allow_m)
    res = run_simulation(
        params, t_h, n_s, k_sw, c_basis, cfg.get("seed", 42), allow_mixed_basis=allow_m
    )

    summary = compute_summary_metrics(res)
    json.dump(summary, open(out / "summary.json", "w", encoding="utf-8"), indent=2)
    pd.DataFrame([summary]).to_csv(out / "summary.csv", index=False)
    compute_prcc(res.sampled_params, res.final_net_balances).to_csv(out / "prcc.csv", index=False)
    compute_tornado(params, t_h, k_sw, c_basis).to_csv(out / "tornado.csv", index=False)
    compute_conditions_table(res).to_csv(out / "conditions.csv", index=False)
    json.dump(
        _metadata(cfg, Path(args.parameters), Path(args.config), res),
        open(out / "run_metadata.json", "w", encoding="utf-8"),
        indent=2,
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
    c_basis, seed = cfg.get("cost_basis", "global_withdrawal"), cfg.get("seed", 42)
    allow_m = args.allow_mixed_basis or cfg.get("allow_mixed_basis", False)

    r0 = run_simulation(params, t_h, n_s, 0.0, c_basis, seed, 0, allow_m)
    r1 = run_simulation(params, t_h, n_s, 1.0, c_basis, seed, 1, allow_m)

    plot_breakeven_distribution(r0, out / "fig1_breakeven_dist")
    plot_probability_vs_horizon(r0, out / "fig2_p_breakeven_horizon")
    plot_net_balance_fan_chart(r0, out / "fig3_net_balance_fan")
    plot_tornado_chart(
        compute_tornado(params, t_h, 0.0, c_basis),
        out / "fig4_tornado",
        r0.has_placeholder,
        r0.is_mixed_basis,
    )
    plot_scope_comparison(r0, r1, out / "fig5_scope_comparison")
    print(f"Figures written to {out}")
    return 0


def cmd_reproduce(args: argparse.Namespace) -> int:
    return cmd_validate(args) or cmd_run(args) or cmd_figures(args)


def main() -> None:
    p = argparse.ArgumentParser(
        prog="ai-water-breakeven", description="Monte Carlo break-even model"
    )
    sub = p.add_subparsers(dest="command", required=True)
    for name, fn in [
        ("validate", cmd_validate),
        ("run", cmd_run),
        ("figures", cmd_figures),
        ("reproduce", cmd_reproduce),
    ]:
        sp = sub.add_parser(name)
        sp.add_argument("--parameters", default="data/parameters.csv")
        sp.add_argument("--config", default="configs/base.toml")
        sp.add_argument("--strict", action="store_true")
        sp.add_argument("--allow-mixed-basis", action="store_true")
        if name in ("run", "figures", "reproduce"):
            sp.add_argument("--out-dir", default="results")
            sp.add_argument("--samples", type=int, default=None)
        if name in ("run", "reproduce"):
            sp.add_argument("--horizon", type=int, default=None)

    args = p.parse_args()
    cmds = {
        "validate": cmd_validate,
        "run": cmd_run,
        "figures": cmd_figures,
        "reproduce": cmd_reproduce,
    }
    sys.exit(cmds[args.command](args))


if __name__ == "__main__":
    main()
