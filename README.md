# AI Water Break-Even

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

- `summary.csv` and `summary.json`: Probabilities of sustained break-even across horizons (10, 20, 30, 50 years) with Monte Carlo standard errors, probability of never breaking even, success horizon quantiles, and pathway benefit shares.
- `prcc.csv`: Partial Rank Correlation Coefficients of continuous parameters against final net balance.
- `tornado.csv`: One-at-a-time low/high parameter sensitivity swings on final net water balance.
- `conditions.csv`: Parameter medians and interquartile ranges stratified by 30-year break-even success versus failure.
- `run_metadata.json`: Provenance record including git commit hash, dependency versions, random seed, execution timestamp, and SHA-256 hashes of input parameters and configuration files.
- `fig1_breakeven_dist.{png,svg}`: Distribution of sustained break-even years with an explicit censored outcome bar.
- `fig2_p_breakeven_horizon.{png,svg}`: Cumulative sustained break-even probability across evaluation horizons.
- `fig3_net_balance_fan.{png,svg}`: Simulation trajectory fan chart displaying median, 50%, and 90% envelopes.
- `fig4_tornado.{png,svg}`: Ranked horizontal sensitivity swing chart across model inputs.
- `fig5_scope_comparison.{png,svg}`: Break-even probability comparison across direct-only ($k=0$) and full-scope electricity ($k=1$) scenarios.

## Limitations

The model evaluates aggregated volumetric balances and does not account for localized hydrological basin stress. It does not apply intertemporal financial discounting, and parameter attribution shares are user-specified counterfactual modeling choices rather than empirical physical constants. Continuous parameters are sampled independently without macroeconomic correlation structures.

## Citation

```bibtex
@software{ai_water_breakeven_2026,
  title = {AI Water Break-Even: A Monte Carlo Scenario Model},
  author = {Tazwar},
  year = {2026},
  url = {https://github.com/tazwaryayyyy/ai-water-breakeven}
}
```
