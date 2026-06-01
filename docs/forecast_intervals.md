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
| h+1 | 1341 | 403 | 92.1% | 74.7% |
| h+2 | 1341 | 403 | 51.9% | 22.3% |
| h+3 | 1341 | 403 | 54.3% | 24.6% |
| h+4 | 1341 | 403 | 55.3% | 24.6% |
| h+5 | 1341 | 403 | 55.3% | 24.8% |
| h+6 | 1341 | 403 | 55.3% | 24.8% |
| h+7 | 1341 | 403 | 54.6% | 25.6% |
| h+8 | 1341 | 403 | 54.6% | 26.6% |
| h+9 | 1341 | 403 | 55.8% | 28.3% |
| h+10 | 1341 | 403 | 57.1% | 28.5% |
| h+11 | 1341 | 403 | 58.1% | 29.3% |
| h+12 | 1341 | 403 | 58.1% | 30.0% |
| h+13 | 1341 | 403 | 57.1% | 30.3% |
| h+14 | 1341 | 403 | 56.8% | 30.3% |
| h+15 | 1341 | 403 | 56.3% | 30.8% |
| h+16 | 1341 | 403 | 56.1% | 30.5% |
| h+17 | 1341 | 403 | 56.3% | 31.5% |
| h+18 | 1341 | 403 | 57.1% | 32.8% |
| h+19 | 1341 | 403 | 57.6% | 32.5% |
| h+20 | 1341 | 403 | 60.0% | 33.3% |
| h+21 | 1341 | 403 | 61.3% | 33.0% |
| h+22 | 1341 | 403 | 60.0% | 33.0% |
| h+23 | 1341 | 403 | 60.5% | 33.0% |
| h+24 | 1341 | 403 | 60.0% | 32.8% |

## Overall Coverage

| Nominal | Observed OOS | check_n |
|---:|---:|---:|
| 80% | 58.4% | 9672 |
| 50% | 31.2% | 9672 |
