# Limitations

Prose version for the paper. The numbered list in docs/model.md is the source; if the two differ, docs/model.md governs.

The model compares global totals and cannot say where water is saved or lost. It does not weight water by local scarcity, so savings in one basin are not matched to costs in another. Costs use the global scope 1+2 projection of Li et al. (2025) for 2027, grown at an assumed two-phase rate; no source covers growth between 2035 and 2077, which is most of the simulated horizon. Embodied (scope 3) water and the water footprint of the AI-enabled systems themselves are not modeled, except through the pathway water intensity r.

Each benefit pathway either deploys or does not, as one random draw per simulated run. The probability of break-even is therefore bounded above by the probability that at least one pathway deploys, and the deployment probabilities are unsourced placeholders. For this reason results are reported conditional on deployment and as thresholds on attribution and displacement, not as a single probability.

The timing of the solar-driven food pathway (lag L and ramp R) is assumed from the historical diffusion of energy technologies, a different sector. The first commercial hydrogen-fermentation plant reports a design capacity of 160 tonnes of Solein per year (company press release, October 2025). Displacement phi is taken from a cropland-based scenario study that pools several microbial-protein routes (Pikaar et al. 2018), and cropland share is only a proxy for blue-water share.

Attribution alpha is a constant share of each pathway's benefit. It is a modeling assumption, not a measurement. A plausible counterfactual is that the same technology arrives later without AI, which a constant share does not capture. Desalination adds supply and does not reduce consumption, so on the consumption basis its contribution is a supply credit.

Baseline agricultural water use and desalinated output are held constant, rebound is a single factor per pathway, no discounting is applied, and inputs are sampled independently with no correlation structure. While most inputs remain placeholders, every output is illustrative and is stated as "in X% of simulated scenarios under these inputs", not as a real-world probability.