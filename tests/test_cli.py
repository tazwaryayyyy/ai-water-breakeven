"""Tests for CLI subcommands: validate, run, figures, and reproduce."""

import json
from pathlib import Path

from ai_water_breakeven.cli import (
    cmd_figures,
    cmd_knockouts,
    cmd_reproduce,
    cmd_run,
    cmd_threshold,
    cmd_validate,
)


class DummyArgs:
    def __init__(self, **kwargs):
        self.parameters = kwargs.get("parameters", "data/parameters.csv")
        self.config = kwargs.get("config", "configs/base.toml")
        self.out_dir = kwargs.get("out_dir", "results")
        self.samples = kwargs.get("samples", 1000)
        self.horizon = kwargs.get("horizon", 20)
        self.strict = kwargs.get("strict", False)
        self.allow_mixed_basis = kwargs.get("allow_mixed_basis", False)


def test_cli_validate():
    """Test CLI validate subcommand."""
    args = DummyArgs()
    assert cmd_validate(args) == 0

    strict_args = DummyArgs(strict=True)
    assert cmd_validate(strict_args) == 1


def test_cli_run_and_outputs(tmp_path):
    """Test CLI run subcommand generates summary, PRCC, tornado, conditions, and metadata."""
    out_dir = str(tmp_path / "run_out")
    args = DummyArgs(out_dir=out_dir, samples=500, horizon=15)
    ret = cmd_run(args)
    assert ret == 0

    p = Path(out_dir)
    assert (p / "summary.json").is_file()
    assert (p / "summary.csv").is_file()
    assert (p / "prcc.csv").is_file()
    assert (p / "tornado.csv").is_file()
    assert (p / "conditions.csv").is_file()
    assert (p / "net_balance_by_horizon.csv").is_file()
    assert (p / "sourcing_priority.csv").is_file()
    assert (p / "run_metadata.json").is_file()

    with open(p / "run_metadata.json", "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert "git_commit" in meta
    assert "package_versions" in meta
    assert "sha256_parameters_csv" in meta


def test_cli_figures_generation(tmp_path):
    """Test CLI figures subcommand generates both PNG (300 dpi) and SVG for 5 figures."""
    out_dir = str(tmp_path / "figs_out")
    args = DummyArgs(out_dir=out_dir, samples=500, horizon=15)
    ret = cmd_figures(args)
    assert ret == 0

    p = Path(out_dir)
    for fig_name in [
        "fig1_breakeven_dist",
        "fig2_p_breakeven_horizon",
        "fig3_net_balance_fan",
        "fig4_tornado",
        "fig5_scope_comparison",
    ]:
        assert (p / f"{fig_name}.png").is_file()
        assert (p / f"{fig_name}.svg").is_file()


def test_cli_reproduce_pipeline(tmp_path):
    """Test CLI reproduce subcommand executes the full end-to-end pipeline."""
    out_dir = str(tmp_path / "reproduce_out")
    args = DummyArgs(out_dir=out_dir, samples=500, horizon=15)
    ret = cmd_reproduce(args)
    assert ret == 0

    p = Path(out_dir)
    assert (p / "summary.json").is_file()
    assert (p / "fig1_breakeven_dist.png").is_file()
    assert (p / "knockouts.csv").is_file()


def test_cli_knockouts(tmp_path):
    """Knockout output is available as an independent CLI operation."""
    out_dir = str(tmp_path / "knockout_out")
    args = DummyArgs(out_dir=out_dir, samples=200, horizon=15)
    assert cmd_knockouts(args) == 0
    assert (Path(out_dir) / "knockouts.csv").is_file()


def test_cli_threshold(tmp_path):
    """Threshold map is available through the dedicated CLI command."""
    out_dir = str(tmp_path / "threshold_out")
    args = DummyArgs(out_dir=out_dir)
    args.grid, args.n_per_cell, args.x, args.y = 3, 100, "g_global", "phi_solar_food"
    assert cmd_threshold(args) == 0
    assert (Path(out_dir) / "threshold_map.csv").is_file()
