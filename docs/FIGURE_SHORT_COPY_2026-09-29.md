# Focused short-copy handoff

Only Figures 1, 4, 7 and 8 change. Run `python -m compute_tokens.short_copy` for the four PNG/SVG pairs in `polished_figures/short-copy-2026-09-29`. The same text adapter is part of the current-report reproduction path.

Preserved: titles, numeric values, model/axis labels, sources, legends, Figure 4 counts and median/pooled-rate columns, Figure 7 nested segments, and Figure 8's single 2025–27 panel. Source credits remain separate. Existing font sizes are retained; wrapping uses measured text width. Figures 7/8 gain a small amount of plotting height from the shorter subtitles; all coordinates, limits and scales stay unchanged.

Checks: plotted-artist signature before/after text changes; unchanged figure-text sizes and source strings; text bounds and figure-level overlap assertions; visual PNG review. PNG and SVG are exported from the same figure object. No social variants were found in the delivery folder or its non-designer reference subfolder. The designer's `design-ver` folder is excluded. Only eight new files are uploaded to a new subfolder; original files and the Google Doc are untouched.

## Removed detail to retain in article captions / appendix

- Figure 1: explicit API-spending inference method for closed models, the explanation that actual serving costs are not public, the open-model benchmark-method explanation, and references to Sections 1–2. The serving-cost scenario and 2026–27 projection caveats remain in shorter form.
- Figure 4: API pricing dates (Claude August 21 / Codex September 14, 2026), trace dates (April 23–July 24, 2026), retained-cache assumption, pooled-rate formula including short groups, five-primary-active-minute sample eligibility, and explicit statement that known model/tool work is not capped. Human-wait removal and five-minute idle-gap cap remain. The marks explanation is consolidated into the new footer.
- Figure 7: repeated HBM/cumulative-supply description, 5–10× revenue/cost assumption and $5 per GB300-hour reference rental price. $30 API spending and full allocation remain.
- Figure 8: repeated frontier-model/HBM description, explicit $10–$100 spending-sweep description and $5 per GB300-hour reference rental price. The plotted sweep, revenue/serving-cost ratio and repricing clarification remain.

This pass does not assert that the live article already contains every removed detail; it supplies this checklist without editing the document. Detailed assumptions remain in the reproduction repository.
