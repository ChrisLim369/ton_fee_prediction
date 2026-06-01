# Operational Forecast Accuracy

This report measures operational live accuracy from forecasts that were published before outcomes were known. It is separate from in-sample backtests such as `actual_vs_predicted.csv` and `models/rolling_backtest.csv`.

Generated at: 2026-06-01T02:19:34Z
Status: active
Reconciled rows: 20
Pending rows: 28

## Overall

| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 20 | 19,962.80 | 24,403.51 | 4.20 | -0.0895 | 0.9500 | 44,330.44 | 0.5497 |

## By Horizon

| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1h | 1 | 8,516.45 | 8,516.45 | N/A | N/A | 1.0000 | 46,307.50 | N/A |
| 2h | 1 | 27,848.83 | 27,848.83 | N/A | N/A | 1.0000 | 28,313.20 | N/A |
| 3h | 1 | 32,673.71 | 32,673.71 | N/A | N/A | 1.0000 | 90,385.56 | N/A |
| 4h | 1 | 8,113.40 | 8,113.40 | N/A | N/A | 1.0000 | 49,895.54 | N/A |
| 5h | 1 | 34,962.55 | 34,962.55 | N/A | N/A | 1.0000 | 76,857.69 | N/A |
| 6h | 1 | 19,953.89 | 19,953.89 | N/A | N/A | 1.0000 | 24,813.10 | N/A |
| 7h | 1 | 37.50 | 37.50 | N/A | N/A | 1.0000 | 52,265.65 | N/A |
| 8h | 1 | 1,995.01 | 1,995.01 | N/A | N/A | 1.0000 | 49,800.50 | N/A |
| 9h | 1 | 28,609.88 | 28,609.88 | N/A | N/A | 1.0000 | 79,677.64 | N/A |
| 10h | 1 | 1,714.08 | 1,714.08 | N/A | N/A | 1.0000 | 51,674.49 | N/A |
| 11h | 1 | 26,215.57 | 26,215.57 | N/A | N/A | 1.0000 | 74,834.57 | N/A |
| 12h | 1 | 6,751.58 | 6,751.58 | N/A | N/A | 1.0000 | 42,988.06 | N/A |
| 13h | 1 | 29,817.00 | 29,817.00 | N/A | N/A | 1.0000 | 20,751.42 | N/A |
| 14h | 1 | 24,286.90 | 24,286.90 | N/A | N/A | 1.0000 | 26,004.89 | N/A |
| 15h | 1 | 23,929.45 | 23,929.45 | N/A | N/A | 1.0000 | 26,111.72 | N/A |
| 16h | 1 | 56,844.63 | 56,844.63 | N/A | N/A | 0.0000 | 6,974.56 | N/A |
| 17h | 1 | 25,049.88 | 25,049.88 | N/A | N/A | 1.0000 | 24,805.14 | N/A |
| 18h | 1 | 2,934.36 | 2,934.36 | N/A | N/A | 1.0000 | 52,995.38 | N/A |
| 19h | 1 | 13,549.99 | 13,549.99 | N/A | N/A | 1.0000 | 36,564.59 | N/A |
| 20h | 1 | 25,451.32 | 25,451.32 | N/A | N/A | 1.0000 | 24,587.62 | N/A |

## By Actual Cap Status

| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clean | 18 | 20,014.15 | 24,809.55 | 4.20 | -0.0570 | 0.9444 | 45,858.70 | 0.5636 |
| capped | 2 | 19,500.65 | 20,388.38 | N/A | N/A | 1.0000 | 30,576.10 | N/A |

Positive skill score means the model beat the persistence baseline anchored at the last observed fee when the forecast was issued. `N/A` is used for small samples or zero denominators.
