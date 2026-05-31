# Capped Target Diagnostic

This diagnostic does not de-bias or change `target_next_hour_avg_fee`. It separates in-sample holdout metrics by whether the target hour H+1 is currently flagged as capped.

## Coverage

- Current checked-in hourly_features.csv has 1512 rows, 113 capped rows, capped share 7.5%.
- Computed capped rows in current file: 113 / 1,512 (7.5%).
- Capped onset hour: 2026-05-26T12:00:00Z
- Known distribution: before 2026-05-26 = 0%, 2026-05-26 = 50%, 2026-05-27 through 2026-05-30 = 100%, 2026-05-31 = 83%.

## Warnings

- Confounding: Capped rows are concentrated in a recent continuous block, so capped vs clean differences cannot be attributed to truncation bias alone; time/regime effects are confounded.
- Under-flag limit: is_capped_hour reflects the latest collection run metadata only. Earlier capped-looking plateaus such as 2026-03-29 through 2026-04-27 with tx_count exactly 5000 can be under-flagged, but this report does not auto-relabel them because historical per-run cap metadata cannot be restored reliably.
- Plateau summary: tx_count==5000 and is_capped_hour==0 rows = 719, from 2026-03-29T06:00:00Z to 2026-04-28T04:00:00Z.

## Recent Daily Capped Fraction

| Date | Rows | Capped rows | Capped fraction |
| --- | ---: | ---: | ---: |
| 2026-05-22 | 24 | 0 | 0.0% |
| 2026-05-23 | 24 | 0 | 0.0% |
| 2026-05-24 | 24 | 0 | 0.0% |
| 2026-05-25 | 24 | 0 | 0.0% |
| 2026-05-26 | 24 | 12 | 50.0% |
| 2026-05-27 | 24 | 24 | 100.0% |
| 2026-05-28 | 24 | 24 | 100.0% |
| 2026-05-29 | 24 | 24 | 100.0% |
| 2026-05-30 | 24 | 24 | 100.0% |
| 2026-05-31 | 6 | 5 | 83.3% |

## In-Sample Holdout Segments

Target capping is defined as `is_capped_hour` at H+1, where H is the feature hour in `actual_vs_predicted.csv`.
Matched holdout rows: 303
Dropped rows with missing H+1 cap label: 0

| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clean | 190 | 46,038.99 | 69,913.01 | 8.80 | 0.1463 | N/A | N/A | N/A |
| capped | 113 | 101,683.93 | 168,492.73 | 16.36 | 0.3176 | N/A | N/A | N/A |

Small groups with n < 8 report MAPE/R2/skill as N/A. Directional accuracy is N/A here because the holdout file does not carry current-fee anchors.

## Future Work

Real de-biasing requires recollecting affected windows with higher `max_pages` and persisting per-run cap metadata so historical cap labels can be trusted.
