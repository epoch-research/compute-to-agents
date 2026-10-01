# Polished report figures

## Current approved figure order (September 21, 2026)

Use [the current gallery](draft2_text_review/index.html), [combined PDF](draft2_text_review/all_figures.pdf), or [ZIP bundle](draft2-revised-figures.zip). PNG, SVG and PDF files are in `draft2_text_review/figures/`. Order matches the current Draft 2 captions: opening chart (1), P90 curves (2), heatmaps (3), spending distributions (4), token distributions (5), serving-cost/capacity curve (6), cumulative supply (7), spending sensitivity (8), DeepSeek capacity (9). A1 and A2 are unchanged. Rebuild with `.venv/bin/python -m compute_tokens.figure_text_review`. No document edits. The material below describes the older baseline, which is retained separately.

Alternative artwork for all nine report figures, with **Draft 2** terminology reviewed September 17, 2026. The frozen Draft 1 analysis and figure numbering remain the baseline. No Google Doc edits, no new data retrieval, and no changes to prices, timing, session membership, cache accounting, or capacity assumptions.

Terminology follows Draft 2: projected capacity is expressed as **agents**, cost and token-rate denominators as **agent-hours**, and benchmark/data accounting as **agent sessions**, session trees, or session/model groups as appropriate. Labels do not redefine the accounting unit or imply unique individual model instances. Older headline design experiments and original reference images are historical comparisons; the current headline is the [common serving-cost curve](serving_cost_curve/index.html).

Open [the gallery](index.html) for the figures, captions, download links, and expandable originals. [The combined PDF](all_figures.pdf) contains all nine figures. Individual PNGs (240 dpi), editable-text SVGs, and PDFs are under `figures/`. Numeric summaries, full distribution records, and benchmark estimates are in `measurements/`.

Rebuild from the repository root:

```bash
.venv/bin/python -m compute_tokens.polish
```

The source is `src/compute_tokens/polish.py`. It imports the existing analysis functions, regenerates benchmark normalization from frozen source data, checks it against the reference, and runs the existing cost/token regression checks. It does not read reference images to render the new figures. `manifest.json` records source and output hashes. Original renderers and `reference/figures/` remain unchanged.

The reproduction archive includes this README and the renderer, not generated artwork. Run the command above to populate the folder in a fresh checkout. The local outputs here remain available for review and insertion into the report.

## Design and editorial decisions

The Epoch AI Style Guide and Graph Checklist Template informed sentence-case titles, explicit units, consistent comparative scales, clearer labels, restrained color, and separation of a figure's main message from its detailed caption. This is not Epoch-branded artwork, and no Epoch authorship or endorsement is implied.

- Figures 1/A1: consistent log axes; larger panels and labels; redundant marker shapes distinguish hardware; define streaming speed and configured sessions.
- Figures 2/A2: fixed hardware columns and color scale at every speed target; numeric values remain authoritative; missing coverage is never rendered as zero.
- Figure 3: distinct label, distribution, and summary columns avoid marks covering text. Long-context cohorts are labeled as overlapping subsets; median and pooled rates remain distinct. All tails remain visible.
- Figure 4: source-trace comparison, not replay measurements. Keep full ECDF tails and zero, label the nonlinear scales, distinguish curves with line styles, and place numeric summaries below each panel. Do not imply equivalence from overlap.
- Figures 5–7: explicitly cumulative shipments since 2025; projected capacity once deployed, not calendar-year active agents. Scenario ranges are not confidence intervals. Figure 7 uses billions instead of thousands of millions; this changes display units only.
- Detailed definitions, exclusions, dates, and sources are in `captions.md`/`captions.json`, not tiny dense text inside every image. Use the captions with the figures in the report. Alt text is supplied.

## Editorial cautions for the report

The benchmark unit is a configured root session tree, not necessarily one model instance or an active decode request. Figure 4's offline five-minute caps and retained-cache reconstruction do not make the corpora or runtime replay clocks identical. The new wording preserves those distinctions without changing the report itself.

Figure 3's pooled values agree with the report's $18.2/$15.5/$24.3/$50.2 headline rates. Exact scenario arithmetic is preserved; the existing Appendix B4 endpoint-rounding discrepancies remain unresolved and are not corrected by this design pass. The figures use the report's frozen historical prices, not September 16 live tariffs.

See the repository's [methodology](../docs/METHODOLOGY.md), [provenance](../docs/PROVENANCE.md), and [known discrepancies](../docs/DISCREPANCIES.md). The existing public-release gates still apply. Generated artwork is a local review deliverable, not automatically substituted into the report or baseline reproduction.
