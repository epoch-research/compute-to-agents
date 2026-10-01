# Compute to tokens — reproduction repository

Reproduces the **September 29 report figure set: Figures 1–9, A1 and A2**, including the split versions of Figures 2/A1. Also retains the older Draft 1 tables and timing/cache audits supporting the agent-hour estimates. No Google Docs access, model API keys, inference servers, or GPU are required.

**Status:** private review repository at [epoch-research/compute-to-agents](https://github.com/epoch-research/compute-to-agents), not publicly released. The main hourly-cost rates reproduce. Ten numerical endpoints in Appendix B4 differ slightly from full-precision arithmetic; see [known discrepancies](docs/DISCREPANCIES.md). Public release also needs the benchmark-export redistribution review and final report citation metadata described in [release status](docs/RELEASE_STATUS.md).

## Quick start

Use Python 3.12. Install the fully version-pinned environment once:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/reproduce --offline
```

Open **`build/current/index.html`** for the current figures. `build/current/figures/` contains PNG/SVG exports and full-layout references; `build/current/measurements/` contains the numerical data behind every figure. No existing artwork or `polished_figures/` intermediates are required.

`build/index.html` also links the older Draft 1 PNG/SVG/PDF figures, thirteen tables, interactive distributions, gap-sensitivity plots and reconciliation report. Old figure numbering there is historical, not the current article numbering. Use `--legacy-only` only for that earlier set. Offline mode rejects network connections; installation itself requires internet unless packages are cached.

The snapshot is frozen: “latest” inside historical metadata means September 15, 2026 UTC, not today's data. Historical API prices and source latencies remain unchanged. These are API-equivalent spending estimates, not bills or measured GPU utilization.

## Full source rebuild

```bash
.venv/bin/reproduce --mode full --data-dir raw --download --output build/full
```

This explicitly downloads about 2.01 GB: TraceLab v0.0.2 and WEKA at an immutable Hugging Face revision. It checks sizes and SHA-256, reserves working space, and supports interrupted `.part` downloads. Do not commit `raw/`. Allow several minutes and several GB of RAM; the WEKA JSONL is processed one root at a time.

Download or verify the sources separately, without running analysis:

```bash
.venv/bin/python -m compute_tokens.sources --data-dir raw --download
.venv/bin/python -m compute_tokens.sources --data-dir raw
```

To reuse local public data, place the exact files in `raw/` as `syfi_coding_trace_v0.0.2.duckdb` and `weka_traces.jsonl`, then omit `--download`. Files must match `data/sources.json`. The full path reconstructs session groups, clocks, cache categories and costs from raw sources before comparing with frozen numeric references; it does not substitute the quick-build results.

The current figures also consume those reconstructed inputs in full mode. The **722-row InferenceX benchmark snapshot is bundled**, not refetched from a changing live API. HBM projections and historical tariffs are documented input assumptions, not regenerated forecasts. See [source availability and figure coverage](docs/CURRENT_REPRODUCTION.md) for the precise boundaries. No multi-GB GPU telemetry downloads are needed for these figures.

## Checks and optional runtime audit

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compute_tokens.release --check
.venv/bin/reproduce --offline --strict-report
```

The strict report check deliberately exits nonzero while Appendix B4 discrepancies remain unresolved; ordinary builds finish with a visible warning. Neither changes the report.

The separate artifact audit verifies 13 sampled AgentX configurations and optionally request occupancy for five of them:

```bash
.venv/bin/python -m compute_tokens.agentx --data-dir raw/agentx --download
.venv/bin/python -m compute_tokens.agentx --data-dir raw/agentx --download --requests
```

Artifact downloads require a separately authenticated GitHub CLI (`gh auth login`). Only selected ZIP members are fetched via range requests, not entire GPU-metrics archives. Pinned expired artifacts cause a clear failure, never a substitution with newer runs. Existing original artifact directories can be passed without `--download`. No credentials or signed URLs are saved. Request records are optional and never part of the release archive.

## Navigate the repository

- [Current figure manifest](current_report_manifest.json): current numbering, complete/split exports, and per-figure numerical files.
- [Current reproduction guide](docs/CURRENT_REPRODUCTION.md): data acquisition, input provenance, interpretation of measurements and validation boundaries.
- `src/compute_tokens/current_report.py`: current build orchestration; explicit aggregate and benchmark inputs, no workspace-only files.

The standalone design-preview commands below are historical development tools. They are not prerequisites for the main reproduction command and their galleries/numbering may predate the final handoff. Links below open tracked plotting code, not generated galleries. HTML galleries and exported artwork are excluded from Git: generate them locally and open them in your browser, rather than following a GitHub URL. For the current figure set, use the quick-start command and open `build/current/index.html`.

- [Draft 2 figure text review](src/compute_tokens/figure_text_review.py): historical wording and source-credit review; rebuild with `.venv/bin/python -m compute_tokens.figure_text_review`.
- [Polished figures](src/compute_tokens/polish.py): alternative artwork and captions; rebuild with `.venv/bin/python -m compute_tokens.polish`.
- [Headline candidate](src/compute_tokens/headline.py): reference serving-cost curve; rebuild with `.venv/bin/python -m compute_tokens.headline`.
- [Headline alternatives](src/compute_tokens/headline_alternatives.py): capacity overview, sensitivity charts, and numerical matrix; rebuild with `.venv/bin/python -m compute_tokens.headline_alternatives`.
- [Simplified headline options](src/compute_tokens/headline_simple.py): lower-density model comparisons; rebuild with `.venv/bin/python -m compute_tokens.headline_simple`.
- [Continuous headline curves](src/compute_tokens/headline_curves.py): hourly-cost curves; rebuild with `.venv/bin/python -m compute_tokens.headline_curves`.
- [Common serving-cost curve](src/compute_tokens/serving_curve.py): through-2027 curve; rebuild with `.venv/bin/python -m compute_tokens.serving_curve`.
- [Historical report manifest](report_manifest.json): Draft 1 figures/tables, generators, inputs and outputs.
- [Methodology](docs/METHODOLOGY.md): units, denominators, cache scenarios, filters, prices and limitations.
- [Provenance](docs/PROVENANCE.md): source versions, collection windows and upstream attribution.
- `data/`: privacy-minimized numeric inputs and frozen assumptions.
- `reference/`: independent expected measurements and reviewed reference PNGs.
- `src/compute_tokens/`: reusable analysis code; no sibling-repository dependencies.
- `tests/`: synthetic estimator and release checks.

Use an editable installation from the repository checkout; a standalone wheel without the data directories is not the distribution format. Generated output is excluded from Git. `tools/` holds one-time migration utilities and is not required for reproduction.

To create a local review archive: `.venv/bin/python -m compute_tokens.release --archive`. The allowlisted archive excludes raw data, virtual environments, private traces, build directories and Git history. A public-ready archive requires `--public`, which refuses unresolved release gates. This command never publishes or uploads anything.

## Attribution

Our analysis code is licensed under Apache-2.0, with upstream notices retained. Third-party data is not relicensed by this repository: TraceLab data is provided under CC-BY-4.0, and the SemiAnalysis WEKA dataset is labeled Apache-2.0. InferenceX benchmark measurements come from SemiAnalysis's public API; we have not identified an explicit license covering redistribution of that API snapshot. Source URLs, snapshot dates, and transformations are documented in the provenance files.

Credit TraceLab (SyFI Lab, University of Washington), <https://tracelab.cs.washington.edu>, and SemiAnalysis. Our trace transformations aggregate costs, tokens, and clocks and remove identifying indices. See [NOTICE](NOTICE), [data terms](licenses/DATA_TERMS.md), and [citation guidance](CITATION.md).
