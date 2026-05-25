# Model Evaluation Report

## Summary

- Best model: `gradient_boosted_stumps_200_lr_0_03`
- Selected by: rolling backtest mean R2 (tie-break median RMSE)
- Best model R2: 0.098642
- Best model MAE: 159700.651 nanoton
- Best model RMSE: 214550.785 nanoton
- Best model directional accuracy: 0.703

## Interpretation

Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
          mae          rmse        r2     mape  directional_accuracy                               model_name                        model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
159700.650766 214550.784640  0.098642 6.437749              0.703448      gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none    0.0         580        145        1.0         200.0           0.03              20.0
160404.884066 215313.918451  0.092218 6.462835              0.696552      gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none    0.0         580        145        1.0         100.0           0.05              20.0
164093.344725 219298.857285  0.058306 6.592632              0.675862       gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none    0.0         580        145        1.0          50.0           0.05              20.0
166579.978407 220840.042193  0.045023 6.772587              0.710345 gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none    0.0         580        145        3.0          50.0           0.10              20.0
163825.738990 220923.292541  0.044303 6.605699              0.724138                          ridge_alpha_100                  ridge_regression             none  100.0         580        145        NaN           NaN            NaN               NaN
164807.935569 222533.785687  0.030319 6.621270              0.710345             ridge_alpha_100_log1p_target                  ridge_regression            log1p  100.0         580        145        NaN           NaN            NaN               NaN
164380.640455 222991.066384  0.026329 6.629881              0.717241                           ridge_alpha_10                  ridge_regression             none   10.0         580        145        NaN           NaN            NaN               NaN
165138.199312 224299.983319  0.014865 6.635433              0.717241              ridge_alpha_10_log1p_target                  ridge_regression            log1p   10.0         580        145        NaN           NaN            NaN               NaN
165910.422865 225126.384093  0.007593 6.696389              0.724138                            ridge_alpha_1                  ridge_regression             none    1.0         580        145        NaN           NaN            NaN               NaN
166435.738297 226231.039464 -0.002170 6.692755              0.703448               ridge_alpha_1_log1p_target                  ridge_regression            log1p    1.0         580        145        NaN           NaN            NaN               NaN
176653.563663 226594.939190 -0.005397 7.224391              0.710345                          rolling_mean_6h                             naive             none    0.0         580        145        NaN           NaN            NaN               NaN
202552.248210 271299.792733 -0.441239 8.186842              0.655172                       seasonal_naive_24h                             naive             none    0.0         580        145        NaN           NaN            NaN               NaN
209258.184729 284507.694815 -0.584985 8.593507              0.000000                              persistence                             naive             none    0.0         580        145        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                        model_type target_transform   mean_r2  median_r2   std_r2    min_r2    max_r2      mean_mae    median_mae      std_mae     mean_rmse   median_rmse     std_rmse  mean_mape  median_mape  mean_directional_accuracy  median_directional_accuracy  folds  r2_win_count
     gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none  0.015100   0.035543 0.108036 -0.133905  0.136730 155384.393468 137118.423326 38183.603408 202800.668305 178074.398499 52027.376962   6.312172     5.767891                   0.760417                     0.750000      8             2
     gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none  0.011551   0.032758 0.104966 -0.141904  0.122647 155938.554244 136985.910124 38323.716193 203258.630595 177759.710052 52421.031801   6.328955     5.806811                   0.760417                     0.791667      8             1
gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none -0.033355  -0.067952 0.122086 -0.187591  0.140626 161337.688698 136989.483022 40414.201152 207390.834341 181026.094562 51911.759921   6.601134     5.758501                   0.750000                     0.750000      8             2
      gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none -0.035093  -0.024065 0.101999 -0.190631  0.073499 160509.724316 139929.221145 38770.868675 208151.508871 180225.349645 54012.448811   6.492816     6.019039                   0.744792                     0.750000      8             0
                         ridge_alpha_100                  ridge_regression             none -0.045760  -0.057502 0.160603 -0.232621  0.176092 161675.134971 139962.840750 39459.113288 208304.366725 178218.178996 53093.442164   6.592602     5.874505                   0.750000                     0.729167      8             0
            ridge_alpha_100_log1p_target                  ridge_regression            log1p -0.056738  -0.081004 0.176363 -0.244685  0.177590 162254.375092 142079.335274 40216.595107 209279.676049 180496.563537 53688.390511   6.588918     5.870154                   0.755208                     0.770833      8             2
                          ridge_alpha_10                  ridge_regression             none -0.059141  -0.083985 0.156594 -0.264990  0.149232 163085.821981 141602.565634 40446.035218 209806.835599 181140.625365 53859.101820   6.660660     5.889227                   0.755208                     0.729167      8             0
             ridge_alpha_10_log1p_target                  ridge_regression            log1p -0.067114  -0.087375 0.174759 -0.272151  0.155177 163050.424155 143862.981359 40873.711089 210400.874818 183059.576295 54130.576653   6.631448     5.945237                   0.750000                     0.729167      8             0
                           ridge_alpha_1                  ridge_regression             none -0.068631  -0.084615 0.154152 -0.277745  0.138228 164328.328178 143067.680658 40753.592069 210876.979368 183160.888263 54449.136635   6.716646     5.941222                   0.755208                     0.750000      8             0
              ridge_alpha_1_log1p_target                  ridge_regression            log1p -0.074539  -0.093131 0.174496 -0.283146  0.140843 163923.046911 145686.794350 41034.233988 211218.907326 185320.496193 54524.921652   6.673231     6.017104                   0.744792                     0.729167      8             0
                         rolling_mean_6h                             naive             none -0.162299  -0.090761 0.213654 -0.503229  0.118224 174784.046509 154859.861096 45050.707170 218487.094931 195257.928987 52074.760863   7.187838     6.540500                   0.708333                     0.687500      8             1
                             persistence                             naive             none -0.779450  -0.632516 0.433230 -1.430868 -0.366654 209762.436341 188279.200504 61948.419686 272105.247088 238593.586676 81178.176910   8.627354     7.886207                   0.000000                     0.000000      8             0
```
