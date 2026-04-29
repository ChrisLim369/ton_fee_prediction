# Model Evaluation Report

## Summary

- Best model: `gradient_boosted_stumps_200_lr_0_03`
- Baseline Linear Regression R2: -0.005071
- Best model R2: 0.099493
- R2 change: 0.104564
- MAE change: 6046.710 nanoton
- RMSE change: 12108.736 nanoton

## Interpretation

The best model improved over the plain linear-regression baseline on the chronological holdout split.
Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
          mae          rmse        r2     mape                               model_name                               model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
159571.703049 214449.467666  0.099493 6.431910      gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none    0.0         580        145        1.0         200.0           0.03              20.0
160326.920566 215219.923927  0.093011 6.459443      gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none    0.0         580        145        1.0         100.0           0.05              20.0
164088.536491 219296.511845  0.058326 6.592405       gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none    0.0         580        145        1.0          50.0           0.05              20.0
165616.760923 219747.714972  0.054447 6.729539 gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none    0.0         580        145        3.0          50.0           0.10              20.0
163829.745717 220921.862116  0.044316 6.605857                          ridge_alpha_100                         ridge_regression             none  100.0         580        145        NaN           NaN            NaN               NaN
164812.918522 222533.124467  0.030324 6.621493             ridge_alpha_100_log1p_target                         ridge_regression            log1p  100.0         580        145        NaN           NaN            NaN               NaN
164368.367132 222978.635012  0.026438 6.629369                           ridge_alpha_10                         ridge_regression             none   10.0         580        145        NaN           NaN            NaN               NaN
165131.525859 224290.469833  0.014949 6.635157              ridge_alpha_10_log1p_target                         ridge_regression            log1p   10.0         580        145        NaN           NaN            NaN               NaN
165693.800908 224990.623472  0.008789 6.687880                            ridge_alpha_1                         ridge_regression             none    1.0         580        145        NaN           NaN            NaN               NaN
166275.313542 226105.881197 -0.001062 6.686515               ridge_alpha_1_log1p_target                         ridge_regression            log1p    1.0         580        145        NaN           NaN            NaN               NaN
165618.412672 226558.203527 -0.005071 6.668763                        linear_regression ordinary_least_squares_linear_regression             none    0.0         580        145        NaN           NaN            NaN               NaN
165972.793675 227075.587254 -0.009667 6.664281           linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p    0.0         580        145        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                               model_type target_transform   mean_r2  median_r2   std_r2    min_r2   max_r2      mean_mae    median_mae      std_mae     mean_rmse   median_rmse     std_rmse  mean_mape  median_mape  folds  r2_win_count
     gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none  0.015381   0.036345 0.108205 -0.133905 0.137371 155372.150023 137118.423326 38142.943492 202767.409317 178074.398499 52009.435690   6.311729     5.767891      8             2
     gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none  0.011663   0.032044 0.105270 -0.141904 0.124974 155929.961300 136985.910124 38398.826513 203255.485171 177759.710052 52469.599051   6.328849     5.799699      8             2
gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none -0.023508  -0.062718 0.133605 -0.167049 0.143466 161367.266163 139518.070899 39531.740919 206381.132317 181561.200568 52149.577108   6.596545     5.774972      8             2
      gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none -0.035020  -0.023770 0.102001 -0.190631 0.073499 160500.849606 139929.221145 38762.355960 208142.327471 180225.349645 54002.923643   6.492453     6.019039      8             0
                         ridge_alpha_100                         ridge_regression             none -0.045796  -0.057522 0.160617 -0.232666 0.176137 161678.689975 139971.535688 39454.190712 208307.754594 178220.158029 53093.932378   6.592721     5.874454      8             0
            ridge_alpha_100_log1p_target                         ridge_regression            log1p -0.056779  -0.081014 0.176389 -0.244740 0.177617 162257.233096 142094.212856 40209.920160 209283.119090 180502.902556 53688.215743   6.589031     5.870768      8             2
                          ridge_alpha_10                         ridge_regression             none -0.059018  -0.083826 0.156580 -0.264671 0.149691 163060.168104 141599.373889 40433.731191 209792.762102 181125.931410 53848.302992   6.659649     5.888181      8             0
             ridge_alpha_10_log1p_target                         ridge_regression            log1p -0.067003  -0.087219 0.174747 -0.271844 0.155611 163032.134781 143860.730092 40856.016166 210387.918288 183045.886303 54119.647880   6.630754     5.945144      8             0
                           ridge_alpha_1                         ridge_regression             none -0.067272  -0.082668 0.153551 -0.274108 0.140047 164094.395248 142912.812330 40731.291247 210735.235336 183054.483569 54356.072940   6.707483     5.934321      8             0
                       linear_regression ordinary_least_squares_linear_regression             none -0.071889  -0.089044 0.156623 -0.265568 0.147611 163818.965763 140796.575702 41867.939718 211380.722921 182652.712345 55588.712206   6.691046     5.880239      8             0
              ridge_alpha_1_log1p_target                         ridge_regression            log1p -0.073194  -0.091370 0.173888 -0.279563 0.142598 163725.728284 145501.074764 40977.094744 211079.994125 185205.108205 54433.934995   6.665561     6.009454      8             0
          linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p -0.075639  -0.094247 0.174128 -0.276636 0.147751 163538.736854 143548.158809 41301.654918 211429.185946 185049.248551 55048.724781   6.656294     5.921572      8             0
```
