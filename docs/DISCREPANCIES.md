# Report reconciliation

The main hourly-cost estimates, source distributions and benchmark economics reproduce under the frozen assumptions. No report content has been changed.

## Appendix B4: rounded concurrency used in four rows

Ten range endpoints in the GLM/Kimi rows differ by more than half the displayed last decimal from full-precision calculations. **All ten reported values reproduce when the displayed two-decimal concurrency is used** instead of the full-precision interpolated concurrency. This identifies intermediate rounding as the cause, not a cohort, pricing, or timing change.

| GB300 benchmark scenario | Full-precision clients/GPU | Displayed clients/GPU | 2026 full-precision range, million | 2027 full-precision range, million |
|---|---:|---:|---:|---:|
| GLM 5.2, 50 TPS | 9.458333 | 9.46 | 181.1–319.7 | 372.0–968.7 |
| GLM 5.2, 100 TPS | 7.848830 | 7.85 | 150.3–265.3 | 308.7–803.8 |
| Kimi K3, 50 TPS | 3.971853 | 3.97 | 76.1–134.2 | 156.2–406.8 |
| Kimi K3, 100 TPS | 1.765826 | 1.77 | 33.8–59.7 | 69.5–180.8 |

The largest proportional difference is approximately 0.25%. Main figures and closed-model headline estimates are unaffected. Generated Table B4 uses full precision and `build/tables/reconciliation.json` records every discrepancy. `reference/report_tables.json` preserves the report's original values. Before publication, choose whether to update those report cells or explicitly retain their intermediate-rounding convention; this repository does not make that editorial change automatically.

## Ancillary sample-summary coverage metadata

The old sample-summary file's `coverage` spending totals were calculated with an older price table by an identity-check helper. They are not the Figure 3 numerators. The raw rebuild now emits coverage with the frozen report price overlay, so its corpus-wide coverage-cost fields differ from that old metadata. The six sample rows, 3,390 groups / 3,382 distinct sessions, collection windows, and actual reported pooled rates agree. Never use the old `coverage.priced_round_cost_usd` as the Figure 3 pooled numerator.

## Remaining methodological uncertainty (not numerical mismatches)

WEKA cache hits are reconstructed; source gap caps do not perfectly remove human delays; TraceLab lacks complete root/child linkage; benchmark clients are not pure decode concurrency. These limitations remain documented rather than “fixed” by silently changing definitions. Source-corpus agreement at a five-minute cap does not establish identical hardware replay utilization.
