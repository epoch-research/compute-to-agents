# Release status

## October 1 private review repository

Private repository: <https://github.com/epoch-research/compute-to-tokens-repro>. Visibility was explicitly verified as private before pushing. All 48 tests, the privacy/checksum checks, and a fresh extracted-archive offline reproduction passed again, including all 11 current figures and four split parts. The September 29 short-copy revisions are included. Raw trace datasets, personal traces, credentials, environments and generated build directories are excluded from the upload. The public-release gates remain unresolved; private review is not public publication approval.

## September 29 current-figure audit

The main `reproduce` command now also generates the current **11 figures (1–9, A1–A2)** and four split parts, with per-figure numerical exports and no dependency on ignored design-preview CSVs or old images. Figure 8 is 2025–27 only; 2/A1 share grouped hardware encodings; A2's GLM-5.2/B200 cell is checked at 0.975. Earlier numbering below refers to the historical Draft 1 build.

Validated September 29:

- All **48 tests** pass, including current capacity anchors, HBM arithmetic and downloader guards.
- Full TraceLab/WEKA reconstruction passes against the frozen references: 6,633 cost groups and 5,472 token groups. Every current measurement CSV/JSON agrees between quick and full builds within existing tolerances.
- An unpacked allowlisted archive passes the offline quick build and all tests from an unrelated temporary directory, without design-preview intermediates. All 11 current figures and four split parts are present.
- Both pinned public data URLs respond HTTP 200 to HEAD requests with the exact expected byte lengths. Raw files used in reconstruction were existing checksum-verified copies; a fresh multi-GB network transfer was not repeated. Resume/corruption/opt-in/space handling is covered by mocked transport tests.
- Rendering agrees with the design handoff for 14 of 15 PNGs; Figure 6 differs in 33 antialiasing pixels when using computed inputs directly. Numerical model anchors and curves agree. Portable acceptance is numerical, not pixel identity.

Publication gates below remain unchanged. The updated archive is for local review, not public clearance.

## Historical baseline validation

This is a **local, tested release candidate**, not a published repository. No report edits, GitHub remote, commits, or uploads were made during preparation.

Implemented: standalone package and locked Python environment; offline quick build; checksum-pinned raw-source reconstruction; nine report figures in PNG/SVG/PDF; thirteen tables in CSV/HTML and full-precision JSON; methodology/provenance; optional authenticated AgentX artifact audit; source clock sensitivity; reference PNGs; synthetic/regression tests; CI; allowlisted checksummed archive tooling.

Validated locally with Python 3.12:

- All nine report PNGs reproduce pixel-for-pixel in the pinned environment.
- All 128 distribution/scenario records pass the existing numerical regression checks.
- Raw reconstruction matches all 6,633 priceable TraceLab groups and 5,472 token groups (5,079 TraceLab + 393 WEKA), including 98,827 WEKA calls.
- Source-identity audit confirms 3,390 main model groups / 3,382 distinct sessions and the four source-activity windows.
- Runtime audit matches 13 configurations, five HTTP-occupancy reconstructions, and nine historical harness pins.
- Dependencies install in an isolated environment; `pip check` passes. There are 31 synthetic/regression tests.
- An allowlisted ZIP was unpacked into an unrelated temporary directory. Both the offline quick build and full reconstruction passed there, loading code from the extracted candidate and using raw datasets only through an explicit `--data-dir` argument.
- The release allowlist excludes raw data, private traces, document exports, environments, build files and Git history. Numeric inputs have no contributor/session IDs or raw prefix hashes.

## Before public publication

1. Resolve the small Appendix B4 intermediate-rounding discrepancies, or document the chosen convention. Main figures/headline rates are unchanged. Strict report reconciliation intentionally fails until resolved.
2. Confirm the public benchmark API snapshot's redistribution terms. InferenceX's software license does not by itself establish an API-data license. This is a local staged input, not a claim of cleared rights.
3. Add the final author/report/repository citation metadata and review the publication target.

These are explicit gates in `release_status.json`; `--public` packaging refuses them. A local `LOCAL-REVIEW.zip` can still be generated for inspection. No auto-publishing is implemented.

## Reproducibility boundaries

The full raw reconstruction was tested using existing files whose source checksums match, rather than needlessly downloading another copy of the approximately 2 GB dataset. URL/revision metadata was checked against the public sources. The network downloader has size/checksum/resume guards; fresh end-to-end multi-GB downloads have not been repeated here.

The optional GitHub artifact analysis was tested against saved original artifacts. Its authenticated network range downloader is a separate path, not a prerequisite for report reproduction. Original artifact expiry remains an availability risk. The repository does not bundle a 400 MB copy of raw request logs, or claim this optional audit can be rebuilt forever if GitHub deletes its sources.

Pixel equality is an environment-specific check; numerical equivalence is the portable acceptance criterion. Static hardware-spec tables reproduce frozen cited constants; the repository does not re-measure hardware or recreate proprietary shipment forecasts.
