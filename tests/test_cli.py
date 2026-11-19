"""Tests for CLI subcommands: validate, run, figures, and reproduce."""

import json
from pathlib import Path

import pandas as pd

from ai_water_breakeven import cli
from ai_water_breakeven.cli import (
    cmd_figures,
    cmd_knockouts,
    cmd_reproduce,
    cmd_run,
    cmd_threshold,
    cmd_validate,
)
from ai_water_breakeven.params import load_parameters
from ai_water_breakeven.simulate import compute_knockout_table, run_knockout_scenarios


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
        "fig8_breakeven_given_solar_food",
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


def test_cli_run_writes_conditional_csv(tmp_path):
    """Run writes conditional.csv with one row per pathway and the placeholder notice."""
    out_dir = str(tmp_path / "cond_out")
    args = DummyArgs(out_dir=out_dir, samples=200, horizon=15)
    assert cmd_run(args) == 0
    df = pd.read_csv(Path(out_dir) / "conditional.csv")
    assert list(df["pathway"]) == ["solar_food", "desal", "any"]
    assert (df["publication_notice"] == "PLACEHOLDER INPUTS - NOT FOR PUBLICATION").all()


def test_cli_figures_conditional_watermark(tmp_path):
    """fig8 restricted to solar-food deployment carries the placeholder mark."""
    out_dir = str(tmp_path / "fig8_out")
    args = DummyArgs(out_dir=out_dir, samples=200, horizon=15)
    assert cmd_figures(args) == 0
    p = Path(out_dir)
    assert (p / "fig8_breakeven_given_solar_food.png").is_file()
    svg = (p / "fig8_breakeven_given_solar_food.svg").read_text(encoding="utf-8")
    assert "PLACEHOLDER INPUTS - NOT FOR PUBLICATION" in svg


def test_cli_threshold(tmp_path):
    """Threshold map is available through the dedicated CLI command."""
    out_dir = str(tmp_path / "threshold_out")
    args = DummyArgs(out_dir=out_dir)
    args.grid, args.n_per_cell, args.x, args.y = 3, 100, "g_global", "phi_solar_food"
    assert cmd_threshold(args) == 0
    assert (Path(out_dir) / "threshold_map.csv").is_file()


def test_placeholder_watermark_in_all_outputs_and_strict_fails(tmp_path):
    """Test 9: After non-strict run, every output file has placeholder mark; --strict fails."""
    strict_args = DummyArgs(out_dir=str(tmp_path / "strict_out"), strict=True)
    assert cmd_run(strict_args) == 1

    out_dir = tmp_path / "ph_out"
    args = DummyArgs(out_dir=str(out_dir), samples=200, horizon=15)
    assert cmd_run(args) == 0
    assert cmd_figures(args) == 0
    assert cmd_knockouts(args) == 0
    args.grid, args.n_per_cell, args.x, args.y = 2, 50, "g_global", "phi_solar_food"
    assert cmd_threshold(args) == 0

    csv_files = list(out_dir.glob("*.csv"))
    json_files = list(out_dir.glob("*.json"))
    svg_files = list(out_dir.glob("*.svg"))

    assert len(csv_files) >= 7
    assert len(json_files) >= 2
    assert len(svg_files) >= 7

    for csv_file in csv_files:
        content = csv_file.read_text(encoding="utf-8")
        assert "PLACEHOLDER INPUTS - NOT FOR PUBLICATION" in content, (
            f"Missing mark in {csv_file.name}"
        )

    for json_file in json_files:
        content = json_file.read_text(encoding="utf-8")
        assert "PLACEHOLDER INPUTS - NOT FOR PUBLICATION" in content, (
            f"Missing mark in {json_file.name}"
        )

    for svg_file in svg_files:
        content = svg_file.read_text(encoding="utf-8")
        assert "PLACEHOLDER INPUTS - NOT FOR PUBLICATION" in content, (
            f"Missing mark in {svg_file.name}"
        )


def test_cli_figures_horizon_flag(tmp_path, monkeypatch):
    captured = []
    real_run = cli.run_simulation

    def spy(*a, **kw):
        captured.append(a[1] if len(a) > 1 else kw.get("t_horizon"))
        return real_run(*a, **kw)

    monkeypatch.setattr(cli, "run_simulation", spy)
    args = DummyArgs(out_dir=str(tmp_path / "figs_h"), samples=100, horizon=12)
    assert cmd_figures(args) == 0
    assert captured == [12]


def test_cli_reproduce_threshold_horizon_capped(tmp_path, monkeypatch):
    for name in ("cmd_run", "cmd_figures", "cmd_knockouts"):
        monkeypatch.setattr(cli, name, lambda args: 0)
    seen = []

    def fake_threshold(args):
        seen.append(args.horizon)
        return 0

    monkeypatch.setattr(cli, "cmd_threshold", fake_threshold)
    assert cmd_reproduce(DummyArgs(out_dir=str(tmp_path / "r40"), samples=100, horizon=40)) == 0
    assert cmd_reproduce(DummyArgs(out_dir=str(tmp_path / "r15"), samples=100, horizon=15)) == 0
    assert seen == [30, 30, 15, 15]


def test_cli_threshold_samples_notice(tmp_path, capsys):
    args = DummyArgs(out_dir=str(tmp_path / "th_notice"), samples=100)
    args.grid, args.n_per_cell, args.x, args.y = 2, 50, "g_global", "phi_solar_food"
    assert cmd_threshold(args) == 0
    err = capsys.readouterr().err
    assert "--n-per-cell" in err
    assert "--samples is ignored" in err


def test_cli_knockouts_matches_reference_table(tmp_path):
    out_dir = tmp_path / "ko_ref"
    args = DummyArgs(out_dir=str(out_dir), samples=200, horizon=15)
    assert cmd_knockouts(args) == 0
    written = pd.read_csv(out_dir / "knockouts.csv")
    written = written.drop(columns=["publication_notice"], errors="ignore")
    params = load_parameters("data/parameters.csv")
    reference = compute_knockout_table(
        run_knockout_scenarios(params, t_horizon=15, n_samples=200, seed=42)
    )
    pd.testing.assert_frame_equal(written, reference)


def test_cli_knockouts_short_horizon_figure_fallback(tmp_path):
    out_dir = tmp_path / "ko_short"
    args = DummyArgs(out_dir=str(out_dir), samples=100, horizon=5)
    assert cmd_knockouts(args) == 0
    svg = (out_dir / "fig6_knockouts.svg").read_text(encoding="utf-8")
    assert "P(never sustained break-even within T)" in svg
