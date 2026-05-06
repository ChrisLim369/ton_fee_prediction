# Model Evaluation Report

## Summary

- Best model: `ridge_alpha_100`
- Baseline Linear Regression R2: -18456.470293
- Best model R2: 0.337688
- R2 change: 18456.807981
- MAE change: 89100381.405 nanoton
- RMSE change: 112263766.416 nanoton

## Interpretation

The best model improved over the plain linear-regression baseline on the chronological holdout split.
Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
         mae         rmse            r2         mape                               model_name                               model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
5.907751e+05 6.765409e+05  3.376883e-01 1.073142e+02                          ridge_alpha_100                         ridge_regression             none  100.0         731        183        NaN           NaN            NaN               NaN
6.443156e+05 7.403050e+05  2.069590e-01 1.175147e+02                           ridge_alpha_10                         ridge_regression             none   10.0         731        183        NaN           NaN            NaN               NaN
7.024271e+05 8.085506e+05  5.400537e-02 1.301635e+02             ridge_alpha_100_log1p_target                         ridge_regression            log1p  100.0         731        183        NaN           NaN            NaN               NaN
7.514399e+05 8.670759e+05 -8.789884e-02 1.395016e+02              ridge_alpha_10_log1p_target                         ridge_regression            log1p   10.0         731        183        NaN           NaN            NaN               NaN
7.558275e+05 8.752605e+05 -1.085338e-01 1.389987e+02                            ridge_alpha_1                         ridge_regression             none    1.0         731        183        NaN           NaN            NaN               NaN
8.443986e+05 9.785475e+05 -3.856006e-01 1.572021e+02               ridge_alpha_1_log1p_target                         ridge_regression            log1p    1.0         731        183        NaN           NaN            NaN               NaN
1.123756e+06 1.312054e+06 -1.491023e+00 2.127400e+02 gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none    0.0         731        183        3.0          50.0           0.10              20.0
1.159836e+06 1.357078e+06 -1.664917e+00 2.199908e+02      gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none    0.0         731        183        1.0         200.0           0.03              20.0
1.166788e+06 1.365131e+06 -1.696639e+00 2.213753e+02      gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none    0.0         731        183        1.0         100.0           0.05              20.0
1.196295e+06 1.399840e+06 -1.835507e+00 2.272358e+02       gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none    0.0         731        183        1.0          50.0           0.05              20.0
8.969116e+07 1.129403e+08 -1.845647e+04 1.710570e+04                        linear_regression ordinary_least_squares_linear_regression             none    0.0         731        183        NaN           NaN            NaN               NaN
3.800467e+29 3.387070e+30 -1.660055e+49 6.168451e+25           linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p    0.0         731        183        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                               model_type target_transform       mean_r2  median_r2       std_r2        min_r2    max_r2     mean_mae    median_mae      std_mae    mean_rmse   median_rmse     std_rmse     mean_mape  median_mape  folds  r2_win_count
                         ridge_alpha_100                         ridge_regression             none -4.078699e+00  -2.901693 5.217560e+00 -1.588389e+01 -0.076530 2.479503e+05 181366.710404 2.537276e+05 2.886099e+05 233732.641188 2.634648e+05     38.504906    18.038378      8             1
            ridge_alpha_100_log1p_target                         ridge_regression            log1p -4.126453e+00  -1.673220 7.689119e+00 -2.289784e+01 -0.036826 2.596117e+05 177752.995109 3.218883e+05 2.974605e+05 229252.701011 3.278165e+05     41.935116    13.719589      8             1
             ridge_alpha_10_log1p_target                         ridge_regression            log1p -4.409823e+00  -2.158049 8.019796e+00 -2.400745e+01 -0.080406 2.649424e+05 182797.951489 3.288566e+05 3.052808e+05 235922.868932 3.350130e+05     42.739498    13.564446      8             0
                          ridge_alpha_10                         ridge_regression             none -4.905739e+00  -3.787796 5.664707e+00 -1.638123e+01 -0.137486 2.550652e+05 186701.315329 2.548042e+05 3.018081e+05 242039.953482 2.644421e+05     39.468059    17.649250      8             0
              ridge_alpha_1_log1p_target                         ridge_regression            log1p -5.006899e+00  -2.224217 9.371355e+00 -2.795360e+01 -0.115648 2.765426e+05 184104.457834 3.578838e+05 3.180422e+05 240488.431838 3.626403e+05     45.301723    13.006838      8             0
                           ridge_alpha_1                         ridge_regression             none -6.046669e+00  -4.344606 7.247895e+00 -2.060935e+01 -0.186319 2.723655e+05 189522.712541 2.882262e+05 3.220301e+05 247837.936366 2.967416e+05     43.312289    18.438008      8             0
gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none -1.549970e+01  -1.356060 2.502725e+01 -5.910056e+01  0.112294 3.664619e+05 189396.991330 5.051089e+05 4.028759e+05 237686.480508 4.979062e+05     66.158550    17.497110      8             2
     gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none -6.002657e+01 -13.719269 1.120257e+02 -3.290769e+02 -0.001146 4.896476e+05 220152.599804 5.546387e+05 5.253762e+05 279289.664292 5.390992e+05     92.251128    27.953498      8             2
     gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none -6.423753e+01 -14.296750 1.192369e+02 -3.499132e+02  0.007531 4.989094e+05 220433.821402 5.621330e+05 5.347569e+05 280999.143369 5.461733e+05     94.246738    28.184505      8             0
      gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none -9.158226e+01 -23.595021 1.567709e+02 -4.509450e+02 -0.015173 5.619110e+05 255240.373113 5.792227e+05 5.942833e+05 320232.450104 5.644380e+05    106.992538    40.569330      8             1
                       linear_regression ordinary_least_squares_linear_regression             none -7.329383e+03  -4.013037 2.071927e+04 -5.860696e+04 -0.223373 6.647914e+06 192476.632476 1.831168e+07 6.871078e+06 249900.161833 1.880602e+07   1453.898196    18.341343      8             0
          linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p -2.092189e+09  -2.229969 5.917605e+09 -1.673752e+10 -0.141501 2.195118e+09 185422.371885 6.208301e+09 3.568174e+09 242175.866010 1.009177e+10 502719.786850    12.523560      8             1
```
