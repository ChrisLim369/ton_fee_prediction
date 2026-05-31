# Operational Forecast Accuracy

This report measures operational live accuracy from forecasts that were published before outcomes were known. It is separate from in-sample backtests such as `actual_vs_predicted.csv` and `models/rolling_backtest.csv`.

Generated at: 2026-05-31T12:53:50Z
Status: accumulating
Reconciled rows: 0
Pending rows: 24

The live ledger is still accumulating enough realized forecasts for stable metrics (reconciled n=0).

## Overall

| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

## By Horizon

| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| none | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

## By Actual Cap Status

| Segment | n | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Skill score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clean | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| capped | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

Positive skill score means the model beat the persistence baseline anchored at the last observed fee when the forecast was issued. `N/A` is used for small samples or zero denominators.
