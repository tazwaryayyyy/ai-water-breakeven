# AI Water Break-Even

> **Status:** Inputs marked `PLACEHOLDER` or `MISSING` are unsourced. Outputs are illustrative, not findings. Do not cite them.

This package implements a Monte Carlo scenario model to test what conditions would have to hold for AI-enabled water savings to offset AI's own operational water use. It maps quantitative parameter ranges to break-even timing outcomes rather than forecasting future water balances.

## Installation

Requires Python 3.11 or higher.

```bash
git clone https://github.com/tazwaryayyyy/ai-water-breakeven.git
cd ai-water-breakeven
pip install -e .
```

To install development dependencies:

```bash
pip install -e ".[dev]"
```

## Running the Model

Validate parameter bounds and physical consistency:

```bash
ai-water-breakeven validate
```

Execute a Monte Carlo simulation run:

```bash
ai-water-breakeven run --out-dir results
```

Generate analytical publication figures:

```bash
ai-water-breakeven figures --out-dir results
```

Reproduce the full validation, simulation, and figure pipeline:

```bash
ai-water-breakeven reproduce --out-dir results
```

To enforce strict validation (aborting on any unverified or placeholder input):

```bash
ai-water-breakeven validate --strict
```

## Outputs

All outputs are written to the specified results directory (default: `results/`):

- `summary.csv` and `summary.json`: Probabilities of sustained break-even across horizons (10, 20, 30, 50 years) with Wilson 95% intervals and Monte Carlo standard errors, probability of never breaking even, success horizon quantiles, and pathway benefit shares.
- `prcc.csv`: Partial Rank Correlation Coefficients of continuous parameters against final net balance.
- `tornado.csv`: One-at-a-time low/high parameter sensitivity swings on final net water balance.
- `conditions.csv`: Parameter medians and interquartile ranges stratified by break-even success versus failure at the configurable comparison horizon.
- `cost_trajectory.csv`: Percentiles of cost $C(t)$ and growth ratio $C(t)/C(0)$ at evaluation years 5, 10, 25, and 50.
- `net_balance_by_horizon.csv`: Net balance percentiles at evaluation horizons.
- `sourcing_priority.csv`: Parameters ranked by absolute PRCC with verification status and traceability.
- `knockouts.csv`: Common-random-number scenario metrics under deterministic column overrides.
- `threshold_map.csv`: Two-parameter probability grid evaluations.
- `run_metadata.json`: Provenance record including git commit hash, dependency versions, random seed, execution timestamp, and SHA-256 hashes of input parameters and configuration files.
- `reproduce_status.csv` and `reproduce_manifest.json`: Execution status across all evaluated and skipped region/basis combinations.
- `fig1_breakeven_dist.{png,svg}`: Distribution of sustained break-even years with an explicit censored outcome bar.
- `fig2_p_breakeven_horizon.{png,svg}`: Cumulative sustained break-even probability across evaluation horizons with Wilson intervals.
- `fig3_net_balance_fan.{png,svg}`: Simulation trajectory fan chart displaying median, 50%, and 90% envelopes.
- `fig4_tornado.{png,svg}`: Ranked horizontal sensitivity swing chart across model inputs.
- `fig5_scope_comparison.{png,svg}`: Break-even probability comparison across direct-only ($k=0$) and direct-plus-electricity ($k=1$) scenarios when the selected cost rows separate those scopes.
- `fig6_knockouts.{png,svg}`: Common-random-number knockout scenario break-even probabilities with Wilson intervals.
- `fig7_threshold_map.{png,svg}`: Two-parameter contour threshold map of sustained break-even probability.

## Limitations

The model uses global or national aggregate volumes and cannot represent local watershed scarcity or basin hydrologic conditions. It assumes independent inputs without copulas, excludes Scope 3 embodied water, holds baseline resource demands ($A$ and $D$) constant, and incorporates zero financial discounting. Attribution shares are modeled counterfactual assumptions rather than empirical physical constants.

## Citation

```bibtex
@software{ai_water_breakeven_2026,
  title = {AI Water Break-Even: A Monte Carlo Scenario Model},
  author = {Tazwar},
  year = {2026},
  url = {https://github.com/tazwaryayyyy/ai-water-breakeven}
}
```
