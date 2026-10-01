# September 29 design handoff

Reproduce with `.venv/bin/python -m compute_tokens.design_handoff_revision`.
Outputs: `polished_figures/design-handoff-2026-09-29`, PNG and SVG only.

- Figures 2/A1: shared blue Blackwell, purple Hopper, orange AMD encodings; distinct hardware markers. Faint raw configurations removed, frontier lines/points and guides retained. Complete layouts retained; two split design inputs per figure reproduce the same artists with unchanged limits and logarithmic scales. Each includes the complete legend, labels, source, and footer. No renumbering.
- Figure 4: requested title and adjusted-working-time definition; median/pooled columns and mark explanation unchanged.
- Figure 7: thin full-scenario range with a thick central segment and visible endpoints. Original unrounded coordinates retained, labeled 20–40M / 16–56M and 50–101M / 33–171M.
- Figure 8: only 2025–27 retained and enlarged, with the requested subtitle. Band vertices, $30 reference, limits, logarithmic y-axis and repricing note unchanged.
- Figures 7/8: hardware legend suffixes removed.
- A2: source cell GLM-5.2 / B200 checked as **0.975**, not 0.752. No data changes.

`validation.json` records checks and hardware styles. Split text bounds are asserted; PNG layouts visually reviewed. Other figure content remains unchanged. Updated full layouts are also copied into `full-layout-reference`; originals remain available alongside split versions as requested. Google Doc untouched.
