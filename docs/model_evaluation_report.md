# Model Evaluation Report

## Summary

- Best model: `ridge_alpha_10`
- Baseline Linear Regression R2: -11680.612557
- Best model R2: 0.727154
- R2 change: 11681.339712
- MAE change: 63521255.771 nanoton
- RMSE change: 98827460.596 nanoton

## Interpretation

The best model improved over the plain linear-regression baseline on the chronological holdout split.
Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
         mae         rmse            r2         mape                               model_name                               model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
3.889379e+05 4.799421e+05  7.271542e-01 6.157510e+01                           ridge_alpha_10                         ridge_regression             none   10.0         692        174        NaN           NaN            NaN               NaN
3.896037e+05 4.817812e+05  7.250592e-01 6.101428e+01                            ridge_alpha_1                         ridge_regression             none    1.0         692        174        NaN           NaN            NaN               NaN
4.181154e+05 5.179713e+05  6.822021e-01 6.923711e+01                          ridge_alpha_100                         ridge_regression             none  100.0         692        174        NaN           NaN            NaN               NaN
5.126640e+05 6.423099e+05  5.113153e-01 8.906518e+01              ridge_alpha_10_log1p_target                         ridge_regression            log1p   10.0         692        174        NaN           NaN            NaN               NaN
5.168797e+05 6.537379e+05  4.937712e-01 9.119615e+01             ridge_alpha_100_log1p_target                         ridge_regression            log1p  100.0         692        174        NaN           NaN            NaN               NaN
5.289795e+05 6.627344e+05  4.797422e-01 9.201982e+01               ridge_alpha_1_log1p_target                         ridge_regression            log1p    1.0         692        174        NaN           NaN            NaN               NaN
8.054692e+05 1.078586e+06 -3.780007e-01 1.540542e+02 gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none    0.0         692        174        3.0          50.0           0.10              20.0
8.319170e+05 1.118616e+06 -4.821829e-01 1.600742e+02      gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none    0.0         692        174        1.0         200.0           0.03              20.0
8.367731e+05 1.125171e+06 -4.996049e-01 1.610650e+02      gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none    0.0         692        174        1.0         100.0           0.05              20.0
8.574509e+05 1.151915e+06 -5.717386e-01 1.650769e+02       gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none    0.0         692        174        1.0          50.0           0.05              20.0
6.391019e+07 9.930740e+07 -1.168061e+04 1.373340e+04                        linear_regression ordinary_least_squares_linear_regression             none    0.0         692        174        NaN           NaN            NaN               NaN
1.791581e+33 2.324816e+34 -6.402014e+56 3.560101e+29           linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p    0.0         692        174        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                               model_type target_transform       mean_r2  median_r2       std_r2        min_r2    max_r2     mean_mae    median_mae      std_mae    mean_rmse   median_rmse     std_rmse     mean_mape  median_mape  folds  r2_win_count
                         ridge_alpha_100                         ridge_regression             none -3.065675e+00  -0.328116 5.485395e+00 -1.588389e+01 -0.076530 2.618014e+05 215129.357924 2.482621e+05 3.121814e+05 273704.017143 2.563984e+05     33.830863    10.257138      8             1
            ridge_alpha_100_log1p_target                         ridge_regression            log1p -3.403787e+00  -0.328651 7.908887e+00 -2.289784e+01 -0.036826 2.781820e+05 211436.898431 3.159160e+05 3.264696e+05 272124.254134 3.195016e+05     38.044992    10.210028      8             1
             ridge_alpha_10_log1p_target                         ridge_regression            log1p -3.783488e+00  -0.404300 8.239488e+00 -2.400745e+01 -0.080406 2.872345e+05 217883.111348 3.213135e+05 3.379162e+05 279402.694601 3.249856e+05     38.966200    10.779632      8             0
                          ridge_alpha_10                         ridge_regression             none -3.850095e+00  -0.411130 6.057056e+00 -1.638123e+01 -0.137486 2.699327e+05 220507.070010 2.478267e+05 3.255966e+05 281821.209128 2.553674e+05     34.412830    10.895668      8             0
              ridge_alpha_1_log1p_target                         ridge_regression            log1p -4.481489e+00  -0.480685 9.574209e+00 -2.795360e+01 -0.115648 3.029063e+05 219447.906134 3.489140e+05 3.545008e+05 283113.747632 3.508880e+05     41.832339    11.242893      8             0
                           ridge_alpha_1                         ridge_regression             none -5.071530e+00  -0.469815 7.714684e+00 -2.060935e+01 -0.186319 2.904119e+05 223465.352976 2.799933e+05 3.483523e+05 286372.287289 2.855910e+05     38.386407    11.411118      8             0
gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none -1.419038e+01  -0.310185 2.563498e+01 -5.910056e+01  0.112294 3.863562e+05 216264.941035 4.970954e+05 4.309154e+05 294357.255636 4.872901e+05     62.391290    10.356285      8             2
     gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none -5.661042e+01  -0.176899 1.135851e+02 -3.290769e+02  0.013645 5.023824e+05 229933.825433 5.462737e+05 5.396835e+05 296110.190193 5.301918e+05     87.715760    10.066420      8             1
     gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none -6.067523e+01  -0.160346 1.208860e+02 -3.499132e+02  0.018248 5.113937e+05 230061.122225 5.538293e+05 5.479952e+05 295132.133377 5.376902e+05     89.647136    10.076608      8             1
      gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none -8.569421e+01  -0.120096 1.595904e+02 -4.509450e+02  0.014579 5.578765e+05 232634.519712 5.813552e+05 5.919717e+05 294544.545785 5.643246e+05     99.311542    10.207178      8             2
                       linear_regression ordinary_least_squares_linear_regression             none -7.328509e+03  -0.525897 2.071962e+04 -5.860696e+04 -0.223373 6.668873e+06 223975.347336 1.830320e+07 6.901377e+06 289856.205398 1.879377e+07   1449.261147    11.552430      8             0
          linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p -2.092189e+09  -0.530482 5.917605e+09 -1.673752e+10 -0.141501 2.195146e+09 219810.560692 6.208290e+09 3.568213e+09 285822.361549 1.009175e+10 502716.557828    11.324024      8             0
```
