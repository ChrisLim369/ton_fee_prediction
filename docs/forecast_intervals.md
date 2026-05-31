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
| h+1 | 1321 | 397 | 95.0% | 79.3% |
| h+2 | 1321 | 397 | 94.5% | 79.8% |
| h+3 | 1321 | 397 | 94.2% | 78.8% |
| h+4 | 1321 | 397 | 93.7% | 78.6% |
| h+5 | 1321 | 397 | 93.7% | 79.1% |
| h+6 | 1321 | 397 | 94.2% | 79.8% |
| h+7 | 1321 | 397 | 94.2% | 81.4% |
| h+8 | 1321 | 397 | 94.0% | 81.6% |
| h+9 | 1321 | 397 | 94.2% | 81.4% |
| h+10 | 1321 | 397 | 94.0% | 81.6% |
| h+11 | 1321 | 397 | 92.9% | 81.1% |
| h+12 | 1321 | 397 | 93.5% | 82.1% |
| h+13 | 1321 | 397 | 93.7% | 80.9% |
| h+14 | 1321 | 397 | 93.2% | 80.9% |
| h+15 | 1321 | 397 | 93.5% | 80.9% |
| h+16 | 1321 | 397 | 92.7% | 79.3% |
| h+17 | 1321 | 397 | 92.4% | 78.8% |
| h+18 | 1321 | 397 | 92.4% | 78.8% |
| h+19 | 1321 | 397 | 91.9% | 78.8% |
| h+20 | 1321 | 397 | 92.2% | 82.6% |
| h+21 | 1321 | 397 | 91.9% | 80.6% |
| h+22 | 1321 | 397 | 91.2% | 78.8% |
| h+23 | 1321 | 397 | 91.7% | 77.1% |
| h+24 | 1321 | 397 | 91.2% | 75.3% |

## Overall Coverage

| Nominal | Observed OOS | check_n |
|---:|---:|---:|
| 80% | 93.2% | 9528 |
| 50% | 79.9% | 9528 |
