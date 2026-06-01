# Operational Forecast Accuracy

This report measures operational live accuracy from forecasts that were published before outcomes were known. It is separate from in-sample backtests such as `actual_vs_predicted.csv` and `models/rolling_backtest.csv`.

Generated at: 2026-06-01T05:01:01Z
Status: accumulating
Reconciled rows: 20
Distinct forecast origins: 1
Minimum stable origins: 8
Pending rows: 28

The live ledger is still accumulating enough realized forecasts for stable metrics (distinct origins=1, required=8).

## Overall

| Segment | n | Origins | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Persistence skill | Seasonal 24h MAE | Seasonal skill | Rolling 6h MAE | Rolling skill |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| overall | 20 | 1 | 19,962.80 | 24,403.51 | N/A | N/A | 0.9500 | 44,330.44 | N/A | 48,773.78 | N/A | 21,436.93 | N/A |

## 1-Step Apples-To-Apples

| Segment | n | Origins | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Persistence skill | Seasonal 24h MAE | Seasonal skill | Rolling 6h MAE | Rolling skill |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| horizon=1h | 1 | 1 | 8,516.45 | 8,516.45 | N/A | N/A | 1.0000 | 46,307.50 | N/A | 88,580.87 | N/A | 8,516.45 | N/A |

## By Horizon

| Segment | n | Origins | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Persistence skill | Seasonal 24h MAE | Seasonal skill | Rolling 6h MAE | Rolling skill |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1h | 1 | 1 | 8,516.45 | 8,516.45 | N/A | N/A | 1.0000 | 46,307.50 | N/A | 88,580.87 | N/A | 8,516.45 | N/A |
| 2h | 1 | 1 | 27,848.83 | 27,848.83 | N/A | N/A | 1.0000 | 28,313.20 | N/A | 61,861.85 | N/A | 26,510.75 | N/A |
| 3h | 1 | 1 | 32,673.71 | 32,673.71 | N/A | N/A | 1.0000 | 90,385.56 | N/A | 6,742.31 | N/A | 35,561.61 | N/A |
| 4h | 1 | 1 | 8,113.40 | 8,113.40 | N/A | N/A | 1.0000 | 49,895.54 | N/A | 89,661.88 | N/A | 4,928.42 | N/A |
| 5h | 1 | 1 | 34,962.55 | 34,962.55 | N/A | N/A | 1.0000 | 76,857.69 | N/A | 1,960.20 | N/A | 22,033.73 | N/A |
| 6h | 1 | 1 | 19,953.89 | 19,953.89 | N/A | N/A | 1.0000 | 24,813.10 | N/A | 64,027.60 | N/A | 30,010.85 | N/A |
| 7h | 1 | 1 | 37.50 | 37.50 | N/A | N/A | 1.0000 | 52,265.65 | N/A | 26,323.76 | N/A | 2,558.30 | N/A |
| 8h | 1 | 1 | 1,995.01 | 1,995.01 | N/A | N/A | 1.0000 | 49,800.50 | N/A | 34,679.29 | N/A | 5,023.45 | N/A |
| 9h | 1 | 1 | 28,609.88 | 28,609.88 | N/A | N/A | 1.0000 | 79,677.64 | N/A | 95,807.16 | N/A | 24,853.69 | N/A |
| 10h | 1 | 1 | 1,714.08 | 1,714.08 | N/A | N/A | 1.0000 | 51,674.49 | N/A | 40,939.80 | N/A | 3,149.46 | N/A |
| 11h | 1 | 1 | 26,215.57 | 26,215.57 | N/A | N/A | 1.0000 | 74,834.57 | N/A | 41,212.36 | N/A | 20,010.61 | N/A |
| 12h | 1 | 1 | 6,751.58 | 6,751.58 | N/A | N/A | 1.0000 | 42,988.06 | N/A | 41,784.47 | N/A | 11,835.90 | N/A |
| 13h | 1 | 1 | 29,817.00 | 29,817.00 | N/A | N/A | 1.0000 | 20,751.42 | N/A | 1,556.66 | N/A | 34,072.54 | N/A |
| 14h | 1 | 1 | 24,286.90 | 24,286.90 | N/A | N/A | 1.0000 | 26,004.89 | N/A | 24,526.07 | N/A | 28,819.06 | N/A |
| 15h | 1 | 1 | 23,929.45 | 23,929.45 | N/A | N/A | 1.0000 | 26,111.72 | N/A | 102,096.69 | N/A | 28,712.23 | N/A |
| 16h | 1 | 1 | 56,844.63 | 56,844.63 | N/A | N/A | 0.0000 | 6,974.56 | N/A | 161,925.93 | N/A | 61,798.51 | N/A |
| 17h | 1 | 1 | 25,049.88 | 25,049.88 | N/A | N/A | 1.0000 | 24,805.14 | N/A | 46,083.67 | N/A | 30,018.82 | N/A |
| 18h | 1 | 1 | 2,934.36 | 2,934.36 | N/A | N/A | 1.0000 | 52,995.38 | N/A | 13,198.56 | N/A | 1,828.58 | N/A |
| 19h | 1 | 1 | 13,549.99 | 13,549.99 | N/A | N/A | 1.0000 | 36,564.59 | N/A | 10,230.89 | N/A | 18,259.36 | N/A |
| 20h | 1 | 1 | 25,451.32 | 25,451.32 | N/A | N/A | 1.0000 | 24,587.62 | N/A | 22,275.50 | N/A | 30,236.34 | N/A |

## By Actual Cap Status

| Segment | n | Origins | MAE | RMSE | MAPE | R2 | Directional accuracy | Persistence MAE | Persistence skill | Seasonal 24h MAE | Seasonal skill | Rolling 6h MAE | Rolling skill |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| clean | 18 | 1 | 20,014.15 | 24,809.55 | N/A | N/A | 0.9444 | 45,858.70 | N/A | 52,387.17 | N/A | 21,124.61 | N/A |
| capped | 2 | 1 | 19,500.65 | 20,388.38 | N/A | N/A | 1.0000 | 30,576.10 | N/A | 16,253.19 | N/A | 24,247.85 | N/A |

Persistence skill compares against the last observed fee when the forecast was issued. Seasonal skill compares against the actual fee from the same hour 24 hours earlier. Rolling skill compares against the 6-hour mean available at the forecast origin. Stable MAPE/R2/skill require enough distinct forecast origins; `N/A` is used for small samples or zero denominators.
