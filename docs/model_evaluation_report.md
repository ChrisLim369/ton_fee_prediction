# Model Evaluation Report

## Summary

- Best model: `ridge_alpha_100`
- Baseline Linear Regression R2: -7580.689714
- Best model R2: 0.516437
- R2 change: 7581.206151
- MAE change: 55421430.993 nanoton
- RMSE change: 77438040.076 nanoton

## Interpretation

The best model improved over the plain linear-regression baseline on the chronological holdout split.
Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
         mae         rmse            r2         mape                               model_name                               model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
5.194681e+05 6.234192e+05  5.164371e-01 9.196634e+01                          ridge_alpha_100                         ridge_regression             none  100.0         710        178        NaN           NaN            NaN               NaN
5.916390e+05 7.143251e+05  3.651305e-01 1.054551e+02                           ridge_alpha_10                         ridge_regression             none   10.0         710        178        NaN           NaN            NaN               NaN
6.143166e+05 7.450424e+05  3.093554e-01 1.121149e+02             ridge_alpha_100_log1p_target                         ridge_regression            log1p  100.0         710        178        NaN           NaN            NaN               NaN
6.782598e+05 8.248695e+05  1.534294e-01 1.238967e+02              ridge_alpha_10_log1p_target                         ridge_regression            log1p   10.0         710        178        NaN           NaN            NaN               NaN
7.105402e+05 8.698587e+05  5.856547e-02 1.290211e+02                            ridge_alpha_1                         ridge_regression             none    1.0         710        178        NaN           NaN            NaN               NaN
7.840347e+05 9.618349e+05 -1.510489e-01 1.444272e+02               ridge_alpha_1_log1p_target                         ridge_regression            log1p    1.0         710        178        NaN           NaN            NaN               NaN
9.614126e+05 1.205377e+06 -8.077492e-01 1.833794e+02 gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none    0.0         710        178        3.0          50.0           0.10              20.0
9.849646e+05 1.239754e+06 -9.123353e-01 1.886621e+02      gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none    0.0         710        178        1.0         200.0           0.03              20.0
9.895287e+05 1.245794e+06 -9.310131e-01 1.896617e+02      gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none    0.0         710        178        1.0         100.0           0.05              20.0
1.013607e+06 1.274289e+06 -1.020358e+00 1.943007e+02       gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none    0.0         710        178        1.0          50.0           0.05              20.0
5.594090e+07 7.806146e+07 -7.580690e+03 1.116247e+04                        linear_regression ordinary_least_squares_linear_regression             none    0.0         710        178        NaN           NaN            NaN               NaN
8.724578e+22 9.413091e+23 -1.102446e+36 1.327890e+19           linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p    0.0         710        178        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                               model_type target_transform       mean_r2  median_r2       std_r2        min_r2    max_r2     mean_mae    median_mae      std_mae    mean_rmse   median_rmse     std_rmse     mean_mape  median_mape  folds  r2_win_count
                         ridge_alpha_100                         ridge_regression             none -3.471069e+00  -1.319838 5.367565e+00 -1.588389e+01 -0.076530 2.618308e+05 215129.357924 2.482621e+05 3.094730e+05 273704.017143 2.561958e+05     37.505175    14.118693      8             1
            ridge_alpha_100_log1p_target                         ridge_regression            log1p -3.713385e+00  -0.832220 7.815608e+00 -2.289784e+01 -0.036826 2.749454e+05 211436.898431 3.162589e+05 3.204701e+05 272124.254134 3.197506e+05     41.133901    11.154277      8             1
             ridge_alpha_10_log1p_target                         ridge_regression            log1p -4.120493e+00  -1.086487 8.133221e+00 -2.400745e+01 -0.080406 2.844477e+05 217883.111348 3.215756e+05 3.318026e+05 279402.694601 3.252121e+05     42.296814    11.855743      8             0
                          ridge_alpha_10                         ridge_regression             none -4.366563e+00  -1.728185 5.892873e+00 -1.638123e+01 -0.137486 2.721537e+05 220507.070010 2.479692e+05 3.252093e+05 281821.209128 2.553217e+05     38.673846    14.515354      8             0
              ridge_alpha_1_log1p_target                         ridge_regression            log1p -4.814073e+00  -1.472125 9.456355e+00 -2.795360e+01 -0.115648 2.989767e+05 219447.906134 3.493903e+05 3.479718e+05 283113.747632 3.514353e+05     45.111841    12.309318      8             0
                           ridge_alpha_1                         ridge_regression             none -5.618923e+00  -2.633622 7.488683e+00 -2.060935e+01 -0.186319 2.921247e+05 223465.352976 2.800125e+05 3.485874e+05 286372.287289 2.855999e+05     42.721863    16.115865      8             0
gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none -1.431672e+01  -0.749658 2.555797e+01 -5.910056e+01  0.112294 3.744685e+05 212530.279178 5.016318e+05 4.186194e+05 270657.929304 4.918552e+05     64.373000    10.406212      8             2
     gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none -5.667702e+01  -0.374986 1.135473e+02 -3.290769e+02 -0.001146 4.870547e+05 211362.782396 5.561258e+05 5.253341e+05 279217.479099 5.391255e+05     88.832452    14.533189      8             2
     gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none -6.074401e+01  -0.369648 1.208467e+02 -3.499132e+02  0.007531 4.965572e+05 211285.343698 5.634872e+05 5.338298e+05 277318.049561 5.466370e+05     90.855680    14.910784      8             0
      gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none -8.586246e+01  -0.735716 1.594878e+02 -4.509450e+02 -0.015173 5.525465e+05 216968.758105 5.848219e+05 5.831287e+05 275224.409066 5.701049e+05    102.297681    22.151735      8             2
                       linear_regression ordinary_least_squares_linear_regression             none -7.329007e+03  -2.510537 2.071942e+04 -5.860696e+04 -0.223373 6.668813e+06 223975.347336 1.830323e+07 6.898925e+06 289856.205398 1.879475e+07   1453.405429    16.412724      8             0
          linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p -2.092189e+09  -1.650884 5.917605e+09 -1.673752e+10 -0.141501 2.195141e+09 219810.560692 6.208292e+09 3.568205e+09 285441.326374 1.009176e+10 502719.706030    12.263913      8             0
```
