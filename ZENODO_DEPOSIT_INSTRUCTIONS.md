# Zenodo Deposit Instructions (v0.3.0 Release)

This document provides complete metadata and step-by-step instructions for depositing the immutable release of **AI Water Break-Even (v0.3.0)** on [Zenodo](https://zenodo.org/) to mint a permanent Digital Object Identifier (DOI).

> **Status Notice:** No automated Zenodo webhook was configured on the GitHub repository prior to release. In accordance with scientific integrity guidelines, no placeholder DOI has been fabricated in `CITATION.cff` or metadata. Follow these instructions to complete the deposit. Once completed, the repository may be archived.

---

## 1. Release Identification and Provenance

- **Repository:** `https://github.com/tazwaryayyyy/ai-water-breakeven`
- **Release Version:** `v0.3.0`
- **Release Tag:** `v0.3.0`
- **Target Commit SHA:** `c47b2af18f5e33758c22556b2f3ebc9c7749f651`
- **Release Date:** `2026-11-24`
- **Reproduction Archive File:** `results_final_v0.3.0.zip`
- **Archive SHA-256:** `3000470a4abc46126c343f67371b8432b08169626a1d2d6d11b4f84f4642e957`
- **Archive Size:** 2,244,684 bytes (~2.24 MB)

---

## 2. Deposit Metadata for Zenodo

When creating the deposit on [Zenodo New Upload](https://zenodo.org/deposit/new):

- **Digital Object Identifier (DOI):** Allow Zenodo to automatically generate a DOI (click "Reserve DOI").
- **Resource Type:** Software
- **Title:** `AI Water Break-Even: A Monte Carlo Scenario Model (v0.3.0)`
- **Creators / Authors:**
  - **Family Name:** `Tazwar`
  - **Given Name:** `Tazwar`
  - **Affiliation / Alias:** `tazwaryayyyy`
- **Description:**
  ```markdown
  Monte Carlo scenario model examining the conditions under which water benefits attributed to AI would offset the water used by AI computation. The two benefit pathways are desalination (supply-credit interpretation from cost and energy improvements) and solar-driven food production (displacing agricultural crop blue-water consumption). Includes the full v0.3.0 research code, vectorized Latin hypercube simulation engine, threshold surface mapper, Common-Random-Number structural knockout evaluator, complete 100,000-draw consumption-basis reproduction outputs, publication figures (PNG/SVG), and execution provenance metadata.
  ```
- **License:** Open Access — MIT License
- **Version:** `v0.3.0`
- **Language:** English (`eng`)
- **Keywords:**
  - `artificial intelligence`
  - `water resources`
  - `break-even analysis`
  - `monte carlo simulation`
  - `scenario modeling`
  - `computational reproducibility`
- **Related Identifiers:**
  - **URL:** `https://github.com/tazwaryayyyy/ai-water-breakeven` (IsSupplementTo)
  - **DOI:** `10.1145/3724499` (Cites: Li et al., 2025, Communications of the ACM)
  - **DOI:** `10.1016/j.scitotenv.2018.12.076` (Cites: Jones et al., 2019, Sci. Total Environ.)

---

## 3. Files to Upload

Upload the following files to the Zenodo deposit record:
1. `results_final_v0.3.0.zip` (the complete reproduction package containing all CSVs, JSON summaries, SVG/PNG publication figures, parameter variants, environment freeze, and checksum manifest).
2. The GitHub source code archive (`v0.3.0.tar.gz` or `v0.3.0.zip` downloaded from the GitHub Release).

Alternatively, if you enable the Zenodo GitHub Integration:
1. Navigate to [Zenodo GitHub Settings](https://zenodo.org/account/settings/github/).
2. Flip the switch on repository `tazwaryayyyy/ai-water-breakeven`.
3. Publish a release (or republish `v0.3.0`), which triggers Zenodo's automated webhook to pull the code release and mint a permanent DOI.
4. Manually upload `results_final_v0.3.0.zip` to the resulting Zenodo deposit version.

---

## 4. Post-Deposit Verification and Archival

1. Note the minted Zenodo DOI (e.g. `10.5281/zenodo.XXXXXXX`).
2. Verify that the DOI resolves successfully via `https://doi.org/10.5281/zenodo.XXXXXXX`.
3. Optionally add the DOI badge to `README.md` and `doi` field to `CITATION.cff`.
4. Return to the GitHub repository settings:
   - Navigate to `Settings` -> `General` -> `Danger Zone`.
   - Click **Archive repository** to set the repository to read-only state.
