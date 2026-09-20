"""Publication figure generation with colorblind-safe palettes and watermark controls."""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ai_water_breakeven.simulate import SimulationResults

matplotlib.use("Agg")
CB_BLUE, CB_ORANGE, CB_GREEN, CB_VERMILION, CB_GREY, CB_SKY = (
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#D55E00",
    "#7F7F7F",
    "#56B4E9",
)


def _save(fig: plt.Figure, out: Path, has_ph: bool, is_mix: bool) -> None:
    if has_ph:
        fig.text(
            0.5,
            0.5,
            "PLACEHOLDER INPUTS - NOT FOR PUBLICATION",
            fontsize=15,
            color="red",
            alpha=0.22,
            ha="center",
            va="center",
            rotation=25,
            weight="bold",
        )
        fig.text(
            0.5,
            0.01,
            "PLACEHOLDER INPUTS - NOT FOR PUBLICATION",
            fontsize=8,
            color="darkred",
            ha="center",
            weight="bold",
        )
    if is_mix:
        fig.text(
            0.5,
            0.035 if has_ph else 0.01,
            "Warning: Mixed physical basis (cost consumption vs benefit withdrawal)",
            fontsize=8,
            color="darkorange",
            ha="center",
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


def plot_breakeven_distribution(res: SimulationResults, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    counts, _ = np.histogram(
        res.be_years[~np.isnan(res.be_years)], bins=np.arange(1, res.t_horizon + 2) - 0.5
    )
    ax.bar(
        np.arange(1, res.t_horizon + 1),
        counts / res.n_samples,
        width=0.8,
        color=CB_BLUE,
        label="Break-Even Year",
    )
    ax.bar(
        [res.t_horizon + 3],
        [float(np.mean(np.isnan(res.be_years)))],
        width=1.5,
        color=CB_GREY,
        label="Never",
    )
    ticks = list(range(0, res.t_horizon + 1, 10)) + [res.t_horizon + 3]
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(x) for x in ticks[:-1]] + ["Never"])
    ax.set(
        xlabel="Sustained Break-Even Year (yr)",
        ylabel="Probability Share",
        title="Distribution of Sustained Break-Even Horizon",
    )
    ax.legend(frameon=False)
    _save(fig, out, res.has_placeholder, res.is_mixed_basis)


def plot_probability_vs_horizon(res: SimulationResults, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.2))
    t = np.arange(1, res.t_horizon + 1)
    ax.plot(t, [float(np.mean(res.be_years <= s)) for s in t], color=CB_BLUE, lw=2.0)
    ax.set(
        xlabel="Time Horizon (yr)",
        ylabel="Cumulative P(Sustained Break-Even)",
        ylim=(-0.02, 1.02),
        title="Probability of Sustained Break-Even vs. Evaluation Horizon",
    )
    ax.grid(True, linestyle=":", alpha=0.6)
    _save(fig, out, res.has_placeholder, res.is_mixed_basis)


def plot_net_balance_fan_chart(res: SimulationResults, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    t, trj = np.arange(1, res.t_horizon + 1), res.net_balance_trajectories
    ax.fill_between(
        t,
        np.percentile(trj, 5, axis=0),
        np.percentile(trj, 95, axis=0),
        color=CB_SKY,
        alpha=0.3,
        label="5th–95th",
    )
    ax.fill_between(
        t,
        np.percentile(trj, 25, axis=0),
        np.percentile(trj, 75, axis=0),
        color=CB_SKY,
        alpha=0.6,
        label="25th–75th",
    )
    ax.plot(t, np.percentile(trj, 50, axis=0), color=CB_BLUE, lw=2.0, label="Median")
    ax.axhline(0, color="black", linestyle="--", lw=1.0, alpha=0.7)
    ax.set(
        xlabel="Year t (yr)",
        ylabel="Net Cumulative Water Balance N(t) (m^3)",
        title="Net Cumulative Water Balance Trajectories",
    )
    ax.legend(loc="upper left", frameon=False)
    ax.grid(True, linestyle=":", alpha=0.5)
    _save(fig, out, res.has_placeholder, res.is_mixed_basis)


def plot_tornado_chart(
    df: pd.DataFrame, out: Path, has_ph: bool = True, is_mix: bool = False
) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    sub = df.head(10).iloc[::-1]
    y_pos, base = np.arange(len(sub)), sub["base"].iloc[0] if len(sub) > 0 else 0.0
    ax.barh(y_pos - 0.18, sub["val_low"] - base, height=0.35, color=CB_ORANGE, label="Low Bound")
    ax.barh(y_pos + 0.18, sub["val_high"] - base, height=0.35, color=CB_GREEN, label="High Bound")
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sub["parameter"])
    ax.set(
        xlabel="Delta in Final Net Balance N(T) (m^3)",
        title="Sensitivity Swings on Horizon Net Balance",
    )
    ax.legend(frameon=False)
    ax.grid(True, linestyle=":", alpha=0.5)
    _save(fig, out, has_ph, is_mix)


def plot_scope_comparison(r0: SimulationResults, r1: SimulationResults, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.2))
    t = np.arange(1, r0.t_horizon + 1)
    if r0.cost_scope == "scope 1+2 combined":
        ax.plot(
            t,
            [float(np.mean(r0.be_years <= s)) for s in t],
            color=CB_BLUE,
            lw=2.0,
            label="scope 1+2 combined (k not applicable)",
        )
        ax.set(
            xlabel="Time Horizon (yr)",
            ylabel="Cumulative P(Sustained Break-Even)",
            ylim=(-0.02, 1.02),
            title=f"Cost Scope: {r0.cost_scope}",
        )
        ax.legend(frameon=False)
        ax.grid(True, linestyle=":", alpha=0.6)
        _save(fig, out, r0.has_placeholder, r0.is_mixed_basis)
        return
    ax.plot(
        t,
        [float(np.mean(r0.be_years <= s)) for s in t],
        color=CB_BLUE,
        lw=2.0,
        label="k = 0 (Direct)",
    )
    ax.plot(
        t,
        [float(np.mean(r1.be_years <= s)) for s in t],
        color=CB_VERMILION,
        lw=2.0,
        linestyle="--",
        label="k = 1 (Direct + Indirect)",
    )
    ax.set(
        xlabel="Time Horizon (yr)",
        ylabel="Cumulative P(Sustained Break-Even)",
        ylim=(-0.02, 1.02),
        title=f"Scope Comparison: {r0.cost_basis}",
    )
    ax.legend(frameon=False)
    ax.grid(True, linestyle=":", alpha=0.6)
    _save(
        fig, out, r0.has_placeholder or r1.has_placeholder, r0.is_mixed_basis or r1.is_mixed_basis
    )
