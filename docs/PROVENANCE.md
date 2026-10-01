# Frozen source provenance

Numerical baseline: the saved Draft 1 snapshot reviewed September 16, 2026. The current pipeline covers the September 29 figure set (see `CURRENT_REPRODUCTION.md`) using the same frozen source data and pricing. Private document exports, IDs and bridge files are intentionally excluded. The repository does not automatically follow later report edits.

| Input | Frozen source | Notes |
|---|---|---|
| TraceLab | [v0.0.2 release](https://github.com/uw-syfi/TraceLab/releases/tag/v0.0.2), database asset 488289840 | 665,453 rounds; SHA-256 and exact bytes in `data/sources.json`; hash authoritative because the GitHub release is not marked immutable. |
| WEKA | [revision 23f152f6f0f9399a85901b89a6458def0ef16729](https://huggingface.co/datasets/semianalysisai/cc-traces-weka-062126/tree/23f152f6f0f9399a85901b89a6458def0ef16729) | Built June 21, 2026; 393 roots, 98,827 calls. Pinned card and source exclusions in `licenses/WEKA-DATASET-CARD.md`. |
| InferenceX | [public benchmark API](https://inferencex.semianalysis.com/api/v1/benchmarks), fetched September 15, 2026 UTC | 722 frozen agentic records; selected columns only. Original pre-projection hashes and retrieval time in `data/benchmark_projection.json`. Live API contents may differ. |
| AgentX artifact audit | 13 artifact IDs in `fetch_agentx.py`; nine workflow runs | Every inspected run pinned [SemiAnalysis harness 754356e9a39acc6cc6afb242d123bb57c3fb6f75](https://github.com/SemiAnalysisAI/agentx-harness/tree/754356e9a39acc6cc6afb242d123bb57c3fb6f75). Selected member hashes in `reference/agentx_members.json`; raw artifact data not bundled. |
| Tariffs | Saved September 8 overlay; Codex checked September 14; standard trace rates rechecked October 1, 2026 | Standard trace rates still match official listings as of October 1. Original Claude collection date: August 21. Fast-mode fields are not covered by the new date. GLM-5.2/MiniMax M3 selected tariffs also match; DeepSeek/Kimi retain September 15 verification dates. See `data/pricing_verification.json` for scope and sources. Numerical inputs unchanged. |
| Open-model prices/rentals | September 15 snapshot | Explicit rates in `data/assumptions.json`; benchmark API-equivalent billing uses theoretical cache reuse. |
| Hardware/HBM | Sources linked in static Tables 3/C1 and `data/assumptions.json` | Report assumptions, not live specs or newly verified forecasts. |

Included hourly-spending figure run activity (current Figure 4; historical Figure 3) spans April 23–July 24, 2026 UTC. Model-specific windows and overlap aggregates are in `reference/sample_summary.json`, rechecked from source identities during the full build. The source file's collection/release window is not a claim of continuous observation of each contributor.

The utility `command_chains.py` derives from TraceLab commit `4ccd9169b559eaa998396b30580ef81966c07afc`. Interval, cache, session, plotting and audit modules were extracted from the report's local investigation code, with package imports and explicit I/O replacing workspace coupling. Source-analysis arithmetic is retained. `reference/figures/` contains the original reviewed report PNGs; builds do not read them to generate figures.

Quick inputs omit contributor and group indices, transcript text, source-session identifiers and raw prefix hashes. These numeric aggregates are not a formal differential-privacy release; do not attempt to identify contributors. No personal local traces are used. The source datasets themselves remain subject to their published terms.

`release_manifest.json` records byte sizes and SHA-256 for every allowlisted release file. Reference versus rebuilt floating-point values use rtol=1e-10 and atol=1e-8 (the existing distribution regression checks are stricter). Report cells are checked at half the displayed last decimal. Counts and source hashes are exact. Rendering is compared separately from numerical equivalence.
