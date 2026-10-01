# Current report reproduction

Scope: September 29, 2026 handoff, Figures 1–9 and A1–A2. Both parts of 2/A1 keep their article figure numbers. This is a frozen numerical reproduction, not a command to refresh model prices or benchmark results. No document or Drive connection is used.

## Entry points

1. Install Python 3.12 and the pinned dependencies as in the README.
2. `reproduce --offline`: use bundled privacy-minimized aggregates, regenerate normalized benchmark rows, all analyses and current figures.
3. `reproduce --mode full --download --data-dir raw --output build/full`: obtain checksum-pinned source traces, reconstruct aggregates, compare against independent references, then regenerate the same current figures. Previously downloaded matching files are reused.
4. `python -m compute_tokens.sources --data-dir raw --download`: acquisition only. Without `--download`, verify existing files and fail if missing.

Current outputs are under `<output>/current/`. PNG/SVG artwork is convenient for inspection; CSV/JSON numerical equivalence, not exact typography, is the reproducibility target. Full-layout figures and split design inputs share the same computed frontier artists. The renderer regenerates Figure 9 instead of copying an old image, and computes Figures 1/6 anchors instead of reading prior preview outputs.

## Inputs and availability

| Source | Reproduction input | Acquisition and limits |
|---|---|---|
| TraceLab v0.0.2 | Raw DuckDB, 160,182,272 bytes | Public release URL, exact size and SHA-256 in `data/sources.json`; downloaded with explicit opt-in. Checksums detect replacement of a mutable release asset. |
| SemiAnalysis WEKA | Raw JSONL, 1,847,151,435 bytes | Public Hugging Face URL pinned to commit `23f152f6f0f9399a85901b89a6458def0ef16729`; size/SHA-256 verification. |
| InferenceX/AgentX | Bundled `data/inferencex_2026-09-15.csv.gz`, 722 projected benchmark records | Upstream API and original retrieval metadata in `data/benchmark_projection.json`. A current API download cannot recreate a historical response reliably. Do not silently replace this input. Redistribution review is still a public-release gate. |
| Memory supply | `data/assumptions.json` | Frozen cited TrendForce assumptions: annual supply, growth and HBM generation shares. Tests independently reconstruct cumulative HBM3E/HBM4 totals from those assumptions. Not a reproduction of proprietary forecasting research. |
| Prices/rental assumptions | `data/prices.json`, `data/pricing_verification.json`, `data/assumptions.json` | Historical report tariffs and reference rental prices; URLs/dates retained. No live pricing API or LLM credentials needed. |
| Optional runtime audit | Selected GitHub Actions artifact members | Separate `compute_tokens.agentx --download` command requires authenticated `gh`; historical artifact expiry may prevent a fresh audit. Not an input dependency of these 11 figures. |

The network downloader reserves 2 GB beyond each remaining download, retains partial files, resumes only when the server honors the byte range, and refuses corrupt/oversized files. Do not commit raw datasets. Raw transcripts may contain identifying content even though the quick inputs omit it.

## Numerical files by current figure

All paths below are relative to `current/measurements/`.

| Figure | Measurement file | Meaning |
|---|---|---|
| 1 | `figure_1_capacity.csv` | Unrounded central-supply capacity endpoints in **agents**, not millions. Open points use P90 50-token/s GB300 estimates; closed ranges derive from pooled API-equivalent spending divided by 5–10. |
| 2 / A1 | `figure_2_frontiers.csv`, `figure_a1_frontiers.csv` | Original benchmark IDs and selected Pareto-frontier coordinates, with normalized physical-GPU counts. Same points for complete/split layouts. |
| 3 / A2 | `benchmark_target_estimates.csv` | Filter `metric=p90` and `cutoff=50,100` or `200`. Includes interpolation method/coverage metadata, not extrapolated values. A2 GLM-5.2/B200 displays **0.975**. |
| 4 | `distributions.json` | Select `kind=cost`, `dataset=TraceLab`, `scenario=retained`, `clock=cap300`, and `codex_write_markup=true`. Six model/cohort rows, including overlapping whole-group >500k subsets. |
| 5 | `distributions.json` | Select `kind=tokens`, `scenario=retained`, `clock=cap300`, `cohort=shared_pool`. Three token types per dataset. Stored `values` are the full sorted per-group rates before display scaling. |
| 6 | `figure_6_model_anchors.csv`, `figure_6_curve.csv` | Reference serving dollars per agent-hour and capacity in **millions**. Anchor table's open low/high costs correspond to 50/100-token targets; Figure 6 plots only the 50-token endpoint. Closed endpoints are economic scenarios. |
| 7 | `figure_7_ranges.csv` | Unrounded outer and central range endpoints, in millions. |
| 8 | `figure_8_spending_sensitivity.csv` | 2025–27 only; all central/outer band coordinates in millions versus API-equivalent hourly spending. |
| 9 | `figure_9_deepseek.csv` | Capacity endpoints in millions (displayed in billions), both shipment horizons and 50/100-token targets. |

Distribution records retain counts, adjusted hours, total numerator, quantiles and full eligible rates. **Pooled = total numerator / total adjusted hours**, including short groups; percentiles/curves restrict to groups with at least five primary active minutes. Figure 5's TraceLab `n` counts eligible session/model groups; WEKA `n` counts eligible root trees including child calls. These are not interchangeable sampling units. Long-context Figure 4 subsets overlap the parent cohorts; mixed-model source sessions may also appear in more than one model group.

See `METHODOLOGY.md` for source clocks, human waits, five-minute uncovered-gap compression, retained-cache reconstruction, subagent treatment and pricing. These adjustments are not the AgentX replay scheduler's system-wide idle guard. This work does not change those definitions or claim equal capabilities/workloads across models.

## Validation and release boundaries

- Tests cover pinned source sizes/hashes, downloader opt-in/resume/disk guards, clocks/cache arithmetic, distributions, capacity anchors, HBM cumulative arithmetic, current figure coverage and the A2 correction.
- Full mode reconstructs source aggregates before comparing with references; reference images never provide plotted coordinates.
- The fresh-archive smoke test runs without the workspace's ignored `polished_figures/` directory, and requires all 11 current figures and four split parts.
- Historical Draft 1 table reconciliation remains separate: ten Appendix B4 intermediate-rounding discrepancies are reported rather than silently changing the article. No figures/headline estimates are automatically edited.
- Public release remains blocked on benchmark-data redistribution review, historical table reconciliation and final citation metadata. Successful reproduction is not evidence that these publication gates are cleared.
