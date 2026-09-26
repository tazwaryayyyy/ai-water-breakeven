"""Publication figure generation with colorblind-safe palettes and watermark controls."""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ai_water_breakeven.simulate import SimulationResults, wilson_interval

matplotlib.use("Agg")
CB_BLUE, CB_ORANGE, CB_GREEN, CB_VERMILION, CB_GREY, CB_SKY = (
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#D55E00",
    "#7F7F7F",
    "#56B4E9",
)


def _save(
    fig: plt.Figure,
    out: Path,
    has_ph: bool,
    is_mix: bool,
    cost_scope: str | None = None,
) -> None:
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
    if cost_scope:
        fig.text(
            0.99,
            0.01,
            f"Scope: {cost_scope}",
            fontsize=7,
            color="#555555",
            ha="right",
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
    _save(fig, out, res.has_placeholder, res.is_mixed_basis, cost_scope=res.cost_scope)


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
    labels = []
    for h in [10, 20, 30, 50]:
        if h <= res.t_horizon:
            count = int(np.sum(res.be_years <= h))
            low, high = wilson_interval(count, res.n_samples)
            if count == 0 or count == res.n_samples:
                labels.append(f"{h} yr: {count} of {res.n_samples} runs [{low:.3f}, {high:.3f}]")
            else:
                labels.append(f"{h} yr: {count / res.n_samples:.3f} [{low:.3f}, {high:.3f}]")
    if labels:
        ax.text(0.02, 0.98, "\n".join(labels), transform=ax.transAxes, va="top", fontsize=8)
    _save(fig, out, res.has_placeholder, res.is_mixed_basis, cost_scope=res.cost_scope)


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
    _save(fig, out, res.has_placeholder, res.is_mixed_basis, cost_scope=res.cost_scope)


def plot_tornado_chart(
    df: pd.DataFrame,
    out: Path,
    has_ph: bool = True,
    is_mix: bool = False,
    cost_scope: str | None = None,
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
    _save(fig, out, has_ph, is_mix, cost_scope=cost_scope)


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
        _annotate_horizon_probability(ax, r0)
        _save(fig, out, r0.has_placeholder, r0.is_mixed_basis, cost_scope=r0.cost_scope)
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
    _annotate_horizon_probability(ax, r0)
    _save(
        fig,
        out,
        r0.has_placeholder or r1.has_placeholder,
        r0.is_mixed_basis or r1.is_mixed_basis,
        cost_scope=r0.cost_scope,
    )


def plot_knockout_probabilities(
    df: pd.DataFrame, out: Path, has_ph: bool, cost_scope: str | None = None
) -> None:
    """Draw common-random-number knockout probabilities with Wilson intervals."""
    suffix = "yr30" if "p_breakeven_yr30" in df else "yr" + str(
        max(int(c.removeprefix("p_breakeven_yr")) for c in df if c.startswith("p_breakeven_yr"))
    )
    p_col, low_col, high_col = (
        f"p_breakeven_{suffix}",
        f"ci_low_{suffix}",
        f"ci_high_{suffix}",
    )
    sub = df.iloc[::-1]
    values = sub[p_col].to_numpy()
    errors = np.vstack((values - sub[low_col].to_numpy(), sub[high_col].to_numpy() - values))
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(np.arange(len(sub)), values, xerr=errors, color=CB_BLUE, capsize=3)
    ax.set_yticks(np.arange(len(sub)))
    ax.set_yticklabels(sub["scenario"])
    ax.set(
        xlabel=f"P(sustained break-even by {suffix.removeprefix('yr')} yr), 95% Wilson interval",
        xlim=(0, 1),
        title="Common-Random-Number Knockout Scenarios",
    )
    ax.grid(axis="x", linestyle=":", alpha=0.6)
    _save(fig, out, has_ph, False, cost_scope=cost_scope)


def plot_threshold_map(
    df: pd.DataFrame,
    out: Path,
    x_label: str,
    y_label: str,
    has_ph: bool,
    cost_scope: str | None = None,
) -> None:
    """Plot threshold probabilities and requested probability contours."""
    x_values = np.sort(df["x"].unique())
    y_values = np.sort(df["y"].unique())
    z = df.pivot(index="y", columns="x", values="P").reindex(index=y_values, columns=x_values)
    fig, ax = plt.subplots(figsize=(7.5, 5.4))
    image = ax.pcolormesh(x_values, y_values, z.to_numpy(), shading="auto", vmin=0, vmax=1)
    contours = ax.contour(x_values, y_values, z.to_numpy(), levels=[0.1, 0.5, 0.9], colors="black")
    ax.clabel(contours, fmt="%.1f", fontsize=8)
    fig.colorbar(image, ax=ax, label="P(sustained break-even by horizon)")
    ax.set(xlabel=x_label, ylabel=y_label, title="Break-Even Threshold Map")
    _save(fig, out, has_ph, False, cost_scope=cost_scope)


def _annotate_horizon_probability(ax: plt.Axes, res: SimulationResults) -> None:
    """Label the 30-year probability with its Wilson interval, or the last available horizon."""
    horizon = min(30, res.t_horizon)
    count = int(np.sum(res.be_years <= horizon))
    low, high = wilson_interval(count, res.n_samples)
    if count == 0 or count == res.n_samples:
        text = f"{horizon} yr: {count} of {res.n_samples} runs [{low:.3f}, {high:.3f}]"
    else:
        text = f"{horizon} yr: {count / res.n_samples:.3f} [{low:.3f}, {high:.3f}]"
    ax.text(
        0.02,
        0.98,
        text,
        transform=ax.transAxes,
        va="top",
        fontsize=8,
    )
