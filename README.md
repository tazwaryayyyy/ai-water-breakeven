# AI Water Break-Even

Monte Carlo scenario model that asks what conditions would have to hold for AI-enabled water savings to offset AI's own operational water use.

---

> **Status — PLACEHOLDER INPUTS — NOT FOR PUBLICATION**
> Most parameters are still marked `PLACEHOLDER` or `MISSING` in `data/parameters.csv`.
> Every output this tool produces from those inputs carries that notice automatically.
> Numbers in this README's quickstart example are illustrative for the same reason.
> Do not cite any result produced by this model in its current state.

---

## Table of Contents

1. [What this is](#what-this-is)
2. [Quickstart](#quickstart)
3. [Model at a glance](#model-at-a-glance)
4. [Installation](#installation)
5. [CLI reference](#cli-reference)
6. [Outputs](#outputs)
7. [Limitations](#limitations)
8. [Project status](#project-status)
9. [Citation](#citation)
10. [License](#license)

---

## What this is

This model asks a single question: under what combinations of assumptions does the cumulative water benefit enabled by AI (through desalination and solar-assisted food production) exceed AI's own direct operational water consumption? It is a Monte Carlo scenario model, not a point estimate: rather than picking single values for uncertain inputs, it draws many samples from each parameter's stated range and counts how often the net balance crosses zero within a given time horizon. The output is a probability distribution over break-even timing, not a prediction of when — or whether — break-even will occur. This is not a forecast; it is a structured sensitivity analysis of an uncertain future under a set of explicit, traceable assumptions.

---

## Quickstart

### Install

```bash
git clone https://github.com/tazwaryayyyy/ai-water-breakeven.git
cd ai-water-breakeven
pip install -e .
```

### Validate parameters

```bash
ai-water-breakeven validate
```

Real output:

```
Validation passed.
```

### Run a small simulation

The paper configuration uses `N=100000` samples. The example below uses `N=2000` for speed; it is smaller and noisier. The watermark in the output reflects the placeholder input status, not the sample size.

```bash
ai-water-breakeven run --out-dir results_demo --samples 2000 --horizon 50
```

Real output:

```
Run complete. Outputs in results_demo
```

Real `summary.json` from that run (unedited):

```json
{
  "n_samples": 2000,
  "t_horizon": 50,
  "cost_basis": "global_withdrawal",
  "cost_scope": "scope 1+2 combined",
  "k_switch": 0,
  "has_placeholder": true,
  "is_mixed_basis": false,
  "p_breakeven_yr10": 0.0,
  "ci_low_yr10": 0.0,
  "ci_high_yr10": 0.0019170472812529344,
  "count_yr10": 0,
  "count_display_yr10": "0 of 2000 runs",
  "mcse_yr10": null,
  "p_breakeven_yr20": 0.0185,
  "ci_low_yr20": 0.013451349814109875,
  "ci_high_yr20": 0.025394766717736706,
  "count_yr20": 37,
  "mcse_yr20": 0.003013117156700018,
  "p_breakeven_yr30": 0.0805,
  "ci_low_yr30": 0.06936493417594902,
  "ci_high_yr30": 0.0932434684930222,
  "count_yr30": 161,
  "mcse_yr30": 0.006083574196144894,
  "p_breakeven_yr50": 0.1395,
  "ci_low_yr50": 0.1250055929377354,
  "ci_high_yr50": 0.15537659815204802,
  "count_yr50": 279,
  "mcse_yr50": 0.007747249511923571,
  "p_never": 0.8605,
  "ci_low_never": 0.844623401847952,
  "ci_high_never": 0.8749944070622647,
  "count_never": 1721,
  "mcse_never": 0.00774724951192357,
  "be_year_median": 28.0,
  "be_year_p5": 18.0,
  "be_year_p95": 45.099999999999966,
  "n_T_p5": -1.012349548390163e+16,
  "n_T_p25": -40657997780839.84,
  "n_T_p50": -883171341030.8315,
  "n_T_p75": -172717504376.58514,
  "n_T_p95": 468208026345.03235,
  "share_desal_benefit": 0.04478287276380782,
  "share_solar_food_benefit": 0.9552171272361921,
  "publication_notice": "PLACEHOLDER INPUTS - NOT FOR PUBLICATION"
}
```

The `publication_notice` field appears in every output file when any parameter is `PLACEHOLDER` or `MISSING`.

---

## Model at a glance

- **Break-even question.** In each simulated scenario, the model accumulates AI water cost and AI-enabled water benefit year by year and records the first year, if any, when cumulative benefit exceeds cumulative cost. The fraction of scenarios where this happens by year H is the model's estimate of P(break-even by H).
- **Two-phase cost growth.** AI operational water cost is modeled with a first growth phase (rate `g1` for `G1` years) followed by a second phase (rate `g2` for the remainder of the horizon). This allows for slowdown or efficiency gains after initial deployment growth.
- **Region and basis are independent scenario dimensions.** `--region` (`global` or `us`) selects which cost rows to use from `data/parameters.csv`. `--basis` (`withdrawal` or `consumption`) selects whether to measure water by gross withdrawal or net consumption. These are kept separate because the evidence base for each dimension comes from different sources; combining them into a single string would obscure which dimension is uncertain.
- **Two benefit pathways.** AI-enabled desalination and AI-assisted solar food/electro-agriculture are modeled as independent pathways with their own deployment probability, ramp shape, rebound factor, and attribution share. Parameters are placeholders; the pathway structure is fixed.
- **Sourcing priority.** After each run, `sourcing_priority.csv` lists every uncertain parameter ranked by its absolute Partial Rank Correlation Coefficient (|PRCC|) against the final net balance. The parameter with the highest |PRCC| explains the most variance in outcomes and is the highest priority for sourcing a real value.

See [docs/model.md](docs/model.md) for equations, definitions, and assumptions.

---

## Installation

Requires Python >= 3.11.

```bash
git clone https://github.com/tazwaryayyyy/ai-water-breakeven.git
cd ai-water-breakeven
pip install -e .
```

To include development tools (pytest, ruff):

```bash
pip install -e ".[dev]"
```

To include scikit-learn (used internally by PRCC and tornado calculations):

```bash
pip install -e ".[analysis]"
```

---

## CLI reference

All subcommands share these flags:

| Flag | Default | Description |
|---|---|---|
| `--parameters` | `data/parameters.csv` | Path to the parameter CSV |
| `--config` | `configs/base.toml` | Path to the scenario config TOML |
| `--region` | `global` | Cost region: `global` or `us` |
| `--basis` | `withdrawal` | Water accounting basis: `withdrawal` or `consumption` |
| `--strict` | off | Exit 1 if any parameter is `PLACEHOLDER` or `MISSING` |
| `--allow-mixed-basis` | off | Allow cost and benefit rows from different bases |

---

### `validate`

Check parameter bounds and scenario consistency without running a simulation.

```bash
ai-water-breakeven validate
ai-water-breakeven validate --region us --basis consumption
ai-water-breakeven validate --strict
```

Exits 0 if validation passes, 1 if it fails. Prints a one-line result to stdout; errors go to stderr.

---

### `run`

Run the Monte Carlo simulation and write tabular outputs.

```bash
ai-water-breakeven run --out-dir results
ai-water-breakeven run --out-dir results --samples 10000 --horizon 50
ai-water-breakeven run --out-dir results --region us --basis consumption
```

| Flag | Default | Description |
|---|---|---|
| `--out-dir` | `results` | Directory to write output files |
| `--samples` | config `N` (100000) | Number of Monte Carlo draws |
| `--horizon` | config `T` (50) | Time horizon in years |

---

### `figures`

Generate figures fig1–fig5 from a fresh simulation run.

```bash
ai-water-breakeven figures --out-dir results
ai-water-breakeven figures --out-dir results --samples 10000
```

| Flag | Default | Description |
|---|---|---|
| `--out-dir` | `results` | Directory to write figure files |
| `--samples` | config `N` (100000) | Number of Monte Carlo draws |

---

### `knockouts`

Run common-random-number knockout scenarios and write `knockouts.csv` and fig6.

Each knockout scenario fixes one or more parameters to an extreme value while using the same random draws as the baseline. Common random numbers ensure that differences between scenarios reflect the override, not sampling noise.

```bash
ai-water-breakeven knockouts --out-dir results
ai-water-breakeven knockouts --out-dir results --samples 10000 --horizon 30
```

| Flag | Default | Description |
|---|---|---|
| `--out-dir` | `results` | Directory to write output files |
| `--samples` | config `N` (100000) | Number of Monte Carlo draws |
| `--horizon` | config `T` (50) | Time horizon in years |

---

### `threshold`

Sweep two parameters across a grid and record the break-even probability at each cell. Writes `threshold_map.csv` and fig7.

```bash
ai-water-breakeven threshold --out-dir results
ai-water-breakeven threshold --out-dir results --x g_global --y phi_solar_food --horizon 30 --grid 15 --n-per-cell 5000
```

| Flag | Default | Description |
|---|---|---|
| `--out-dir` | `results` | Directory to write output files |
| `--x` | `g_global` | Name of the x-axis parameter |
| `--y` | `phi_solar_food` | Name of the y-axis parameter |
| `--horizon` | `30` | Break-even horizon in years for the probability grid |
| `--grid` | `15` | Number of grid cells per axis |
| `--n-per-cell` | `5000` | Monte Carlo draws per grid cell |

---

### `reproduce`

Run `run`, `figures`, `knockouts`, and `threshold` for every region/basis combination that has complete parameter rows. Combinations with missing required rows are skipped and recorded.

```bash
ai-water-breakeven reproduce --out-dir results
```

| Flag | Default | Description |
|---|---|---|
| `--out-dir` | `results` | Root directory; each non-default combination writes to a subdirectory |

The combination matching `--region`/`--basis` (or the config defaults) writes directly into `--out-dir`. All other complete combinations write to `<out-dir>/<region>_<basis>/`.

---

## Outputs

### Glossary

- **PRCC (Partial Rank Correlation Coefficient).** A rank-based correlation between one input parameter and the final net balance, after removing the linear effect of all other parameters. Values near +1 or -1 indicate the parameter dominates the outcome.
- **Wilson interval.** A 95% confidence interval for a proportion that remains valid even when the count is 0 or N. Used here for break-even probabilities because normal approximations break down at extreme values.
- **Sustained break-even.** The first year in which the cumulative net balance (total benefit minus total cost) turns positive. Requires the cumulative sum to cross zero, not a single-year surplus.
- **Censored outcome.** A simulation run that has not reached break-even by the end of the time horizon T. Counted as "never" in probability tables and excluded from median break-even year calculations.
- **Knockout scenario.** A variant run in which one or more parameters are held at a fixed extreme value (e.g., all deployment probabilities set to 1) while all other parameters use the same random draws as the baseline, isolating the contribution of that parameter group.

---

### Core results

| File | Contents |
|---|---|
| `summary.json` / `summary.csv` | Break-even probabilities at years 10, 20, 30, 50 with Wilson 95% intervals and Monte Carlo standard errors; probability of never breaking even; break-even year quantiles among successful runs; pathway benefit shares |
| `knockouts.csv` | Per-scenario break-even probabilities and change vs baseline for each common-random-number knockout |
| `threshold_map.csv` | P(break-even by horizon) at each cell of the two-parameter grid |
| `net_balance_by_horizon.csv` | Net balance (benefit minus cost) percentiles at years 10, 20, 30, 50 |

---

### Diagnostics

| File | Contents |
|---|---|
| `prcc.csv` | PRCC of each continuous parameter against final net balance, sorted by absolute value |
| `tornado.csv` | One-at-a-time sensitivity swings: final net balance when each parameter moves from its 5th to 95th percentile |
| `conditions.csv` | Parameter medians and interquartile ranges stratified by runs that broke even vs did not by the `conditions_horizon` (default 30 years) |
| `sourcing_priority.csv` | Parameters ranked by |PRCC| with current source status (`sourced`, `PLACEHOLDER`, or `MISSING`) |
| `cost_trajectory.csv` | Percentiles of C(t) and C(t)/C(0) at years 5, 10, 25, 50, showing the two-phase cost growth shape |
| `run_metadata.json` | Git commit hash, timestamp, dependency versions, random seed, SHA-256 hashes of `parameters.csv` and the config TOML |
| `reproduce_status.csv` / `reproduce_manifest.json` | Status of each region/basis combination: `ran` or `skipped`, with missing row names for skipped ones |

---

### Figures

| File | Contents |
|---|---|
| `fig1_breakeven_dist.{png,svg}` | Histogram of first break-even year with a bar for censored (never) outcomes |
| `fig2_p_breakeven_horizon.{png,svg}` | Cumulative break-even probability at each horizon year with Wilson interval bands |
| `fig3_net_balance_fan.{png,svg}` | Fan chart of net balance trajectories at the 5th, 25th, 50th, 75th, and 95th percentiles |
| `fig4_tornado.{png,svg}` | Horizontal bar chart of parameter sensitivity swings, ranked by absolute impact on final net balance |
| `fig5_scope_comparison.{png,svg}` | Break-even probability for k=0 (direct water only) vs k=1 (direct plus electricity-related water) |
| `fig6_knockouts.{png,svg}` | Break-even probability by horizon for each knockout scenario with Wilson error bars |
| `fig7_threshold_map.{png,svg}` | Heatmap of P(break-even by horizon) across the two-parameter grid, with contour lines at 0.1, 0.5, and 0.9 |

Every output file produced from `PLACEHOLDER` or `MISSING` inputs contains the field or column `publication_notice = "PLACEHOLDER INPUTS - NOT FOR PUBLICATION"`.

---

## Limitations

- The model uses global or national aggregate water volumes. It cannot represent local watershed scarcity, basin hydrology, or the geographic distribution of AI infrastructure.
- Inputs are treated as statistically independent. No copula structure is applied across parameters that may be correlated.
- Scope 3 embodied water (manufacturing, supply chain) is excluded. Cost rows for the global region represent scope 1+2 combined.
- Baseline resource demands (agricultural area `A` and desalination capacity `D`) are held constant over the horizon. Demand growth is not modeled.
- No financial discounting is applied to water volumes.
- Attribution shares (the fractions `phi` and `theta` crediting AI for water savings) are modeled counterfactual assumptions, not measured physical constants. Different attribution choices substantially affect the result.
- **Region-matching assumption.** Global benefit rows may be paired with any cost region. This is a named modeling assumption: it means the global benefit estimate is applied even when the cost region is restricted to the US. This assumption is not verified geographically and should be stated explicitly in any write-up.

---

## Project status

Most inputs in `data/parameters.csv` are still marked `PLACEHOLDER` or `MISSING`. No result produced by this model should be treated as a finding until those inputs are replaced with sourced, traceable values. After running the model, `sourcing_priority.csv` provides a live ranked list of which parameters most affect the outcome and therefore most urgently need real values. The numbers in the quickstart example above are illustrative for the same reason.

---

## Citation

Primary data source:

> Li, P., Yang, J., Islam, Md. A., & Ren, S. (2025). Making AI less "thirsty": Uncovering and addressing the secret water footprint of AI models. *Communications of the ACM*, 68(7), 54–61.

If you use this model or code, please cite:

```bibtex
@software{ai_water_breakeven_2026,
  title  = {AI Water Break-Even: A Monte Carlo Scenario Model},
  author = {Tazwar},
  year   = {2026},
  url    = {https://github.com/tazwaryayyyy/ai-water-breakeven}
}
```

No DOI has been verified for the software entry. See `CITATION.cff` for the full machine-readable citation record.

---

## License

MIT License. Copyright (c) 2026 Tazwar. See `LICENSE` for the full text.
