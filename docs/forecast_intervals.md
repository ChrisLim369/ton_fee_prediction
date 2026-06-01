# Forecast Prediction Intervals

These intervals are empirical in-sample estimates from historical recursive forecast replay residuals.
They are not calibrated from live operational residuals yet.

## Method

- For each historical anchor, the saved best model is replayed recursively for 24 hours.
- Residuals are grouped by forecast horizon.
- 80% intervals use the horizon residual q10/q90; 50% intervals use q25/q75.
- Fees are clamped at zero and interval rows are clipped so 80% contains 50% and the point forecast.

## Limitations

If the selected model is a naive baseline, these replay residuals are close to an unbiased empirical error sample.
For trained models, the same checked-in history also informed training, so intervals may be optimistically narrow.
Once S1 forecast_accuracy.csv has enough live residuals per horizon, recalibrate these bands from operational errors.

## Calibration

Out-of-sample calibration: quantiles are fit on earlier anchors, then coverage is measured on held-out later anchors.
Configuration: method=out_of_sample_chronological, fit_fraction=0.7.
Unlike in-sample quantile coverage, these observed values are not guaranteed to equal the nominal 80% or 50%.

| Horizon | total_n | check_n | 80% observed OOS | 50% observed OOS |
|---:|---:|---:|---:|---:|
| h+1 | 1341 | 403 | 95.0% | 78.4% |
| h+2 | 1341 | 403 | 94.5% | 78.7% |
| h+3 | 1341 | 403 | 94.3% | 77.7% |
| h+4 | 1341 | 403 | 93.8% | 77.4% |
| h+5 | 1341 | 403 | 93.8% | 77.7% |
| h+6 | 1341 | 403 | 94.0% | 79.9% |
| h+7 | 1341 | 403 | 94.3% | 80.4% |
| h+8 | 1341 | 403 | 94.0% | 81.6% |
| h+9 | 1341 | 403 | 94.3% | 81.1% |
| h+10 | 1341 | 403 | 93.8% | 81.6% |
| h+11 | 1341 | 403 | 93.1% | 80.9% |
| h+12 | 1341 | 403 | 93.3% | 81.9% |
| h+13 | 1341 | 403 | 93.8% | 80.1% |
| h+14 | 1341 | 403 | 93.3% | 81.4% |
| h+15 | 1341 | 403 | 93.5% | 81.9% |
| h+16 | 1341 | 403 | 92.8% | 78.7% |
| h+17 | 1341 | 403 | 92.6% | 79.4% |
| h+18 | 1341 | 403 | 92.6% | 79.9% |
| h+19 | 1341 | 403 | 92.1% | 79.4% |
| h+20 | 1341 | 403 | 92.1% | 81.6% |
| h+21 | 1341 | 403 | 91.8% | 79.4% |
| h+22 | 1341 | 403 | 91.3% | 79.2% |
| h+23 | 1341 | 403 | 91.8% | 76.7% |
| h+24 | 1341 | 403 | 91.3% | 76.2% |

## Overall Coverage

| Nominal | Observed OOS | check_n |
|---:|---:|---:|
| 80% | 93.2% | 9672 |
| 50% | 79.6% | 9672 |
