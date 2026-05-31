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

| Horizon | n | 80% observed | 50% observed |
|---:|---:|---:|---:|
| h+1 | 1321 | 80.0% | 50.0% |
| h+2 | 1321 | 80.0% | 50.0% |
| h+3 | 1321 | 80.0% | 50.0% |
| h+4 | 1321 | 80.0% | 50.0% |
| h+5 | 1321 | 80.0% | 50.0% |
| h+6 | 1321 | 80.0% | 50.0% |
| h+7 | 1321 | 80.0% | 50.0% |
| h+8 | 1321 | 80.0% | 50.0% |
| h+9 | 1321 | 80.0% | 50.0% |
| h+10 | 1321 | 80.0% | 50.0% |
| h+11 | 1321 | 80.0% | 50.0% |
| h+12 | 1321 | 80.0% | 50.0% |
| h+13 | 1321 | 80.0% | 50.0% |
| h+14 | 1321 | 80.0% | 50.0% |
| h+15 | 1321 | 80.0% | 50.0% |
| h+16 | 1321 | 80.0% | 50.0% |
| h+17 | 1321 | 80.0% | 50.0% |
| h+18 | 1321 | 80.0% | 50.0% |
| h+19 | 1321 | 80.0% | 50.0% |
| h+20 | 1321 | 80.0% | 50.0% |
| h+21 | 1321 | 80.0% | 50.0% |
| h+22 | 1321 | 80.0% | 50.0% |
| h+23 | 1321 | 80.0% | 50.0% |
| h+24 | 1321 | 80.0% | 50.0% |

## Overall Coverage

| Nominal | Observed | n |
|---:|---:|---:|
| 80% | 80.0% | 31704 |
| 50% | 50.0% | 31704 |
