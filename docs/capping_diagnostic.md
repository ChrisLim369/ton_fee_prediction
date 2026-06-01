# Capped Target Diagnostic

This diagnostic does not de-bias or change `target_next_hour_avg_fee`. It separates in-sample holdout metrics by whether the target hour H+1 is currently flagged as capped.

## Coverage

- Current checked-in hourly_features.csv has 1512 rows, 113 capped rows, capped share 7.5%.
- Computed capped rows in current file: 115 / 1,532 (7.5%).
- Capped onset hour: 2026-05-26T12:00:00Z
- Known distribution: before 2026-05-26 = 0%, 2026-05-26 = 50%, 2026-05-27 through 2026-05-30 = 100%, 2026-05-31 = 83%.

## Warnings

- Confounding: Capped rows are concentrated in a recent continuous block, so capped vs clean differences cannot be attributed to truncation bias alone; time/regime effects are confounded.
- Under-flag limit: Per-run collection caps are now persisted as collection_cap, and new rows are flagged with tx_count>=collection_cap. Legacy rows with missing collection_cap can remain under-flagged until an R2 raw replay rebuilds those hours from archived raw data; this report does not auto-relabel them.
- Plateau summary: tx_count==5000 and is_capped_hour==0 rows = 719, from 2026-03-29T06:00:00Z to 2026-04-28T04:00:00Z.

## Recent Daily Capped Fraction

| Date | Rows | Capped rows | Capped fraction |
| --- | ---: | ---: | ---: |
| 2026-05-23 | 24 | 0 | 0.0% |
| 2026-05-24 | 24 | 0 | 0.0% |
| 2026-05-25 | 24 | 0 | 0.0% |
| 2026-05-26 | 24 | 12 | 50.0% |
| 2026-05-27 | 24 | 24 | 100.0% |
| 2026-05-28 | 24 | 24 | 100.0% |
| 2026-05-29 | 24 | 24 | 100.0% |
| 2026-05-30 | 24 | 24 | 100.0% |
| 2026-05-31 | 24 | 5 | 20.8% |
| 2026-06-01 | 2 | 2 | 100.0% |

## In-Sample Holdout Segments

Target capping is defined as `is_capped_hour` at H+1, where H is the feature hour in `actual_vs_predicted.csv`.
Matched holdout rows: 307
Dropped rows with missing H+1 cap label: 0

| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clean | 192 | 44,550.38 | 66,117.06 | 8.61 | 0.2075 | N/A | N/A | N/A |
| capped | 115 | 89,227.35 | 153,476.65 | 13.96 | 0.4285 | N/A | N/A | N/A |

Small groups with n < 8 report MAPE/R2/skill as N/A. Directional accuracy is N/A here because the holdout file does not carry current-fee anchors.

## Future Work

New rows persist per-run caps in `collection_cap` and use `tx_count>=collection_cap` for capping. Legacy rows where `collection_cap` is missing should be corrected by R2 raw replay rather than heuristic relabeling.
