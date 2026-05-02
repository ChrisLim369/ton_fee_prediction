# Model Evaluation Report

## Summary

- Best model: `ridge_alpha_100`
- Baseline Linear Regression R2: -6325.645336
- Best model R2: 0.659591
- R2 change: 6326.304928
- MAE change: 20306546.980 nanoton
- RMSE change: 54462013.465 nanoton

## Interpretation

The best model improved over the plain linear-regression baseline on the chronological holdout split.
Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
         mae         rmse            r2         mape                               model_name                               model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
2.860217e+05 4.024433e+05  6.595912e-01 3.157828e+01                          ridge_alpha_100                         ridge_regression             none  100.0         652        164        NaN           NaN            NaN               NaN
2.981218e+05 4.165025e+05  6.353918e-01 3.250372e+01                           ridge_alpha_10                         ridge_regression             none   10.0         652        164        NaN           NaN            NaN               NaN
3.197256e+05 4.571855e+05  5.606848e-01 3.707839e+01                            ridge_alpha_1                         ridge_regression             none    1.0         652        164        NaN           NaN            NaN               NaN
3.162559e+05 4.641932e+05  5.471140e-01 3.909007e+01             ridge_alpha_100_log1p_target                         ridge_regression            log1p  100.0         652        164        NaN           NaN            NaN               NaN
3.302765e+05 4.811304e+05  5.134618e-01 4.052444e+01              ridge_alpha_10_log1p_target                         ridge_regression            log1p   10.0         652        164        NaN           NaN            NaN               NaN
3.502270e+05 5.233876e+05  4.242444e-01 4.476528e+01               ridge_alpha_1_log1p_target                         ridge_regression            log1p    1.0         652        164        NaN           NaN            NaN               NaN
4.105193e+05 6.696488e+05  5.749104e-02 5.995318e+01 gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none    0.0         652        164        3.0          50.0           0.10              20.0
4.045217e+05 6.764917e+05  3.813031e-02 6.058974e+01      gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none    0.0         652        164        1.0         200.0           0.03              20.0
4.067610e+05 6.813058e+05  2.439159e-02 6.104977e+01      gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none    0.0         652        164        1.0         100.0           0.05              20.0
4.168445e+05 6.995112e+05 -2.844400e-02 6.282028e+01       gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none    0.0         652        164        1.0          50.0           0.05              20.0
2.059257e+07 5.486446e+07 -6.325645e+03 4.516778e+03                        linear_regression ordinary_least_squares_linear_regression             none    0.0         652        164        NaN           NaN            NaN               NaN
4.325146e+28 5.341830e+29 -5.997517e+47 1.034961e+25           linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p    0.0         652        164        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                               model_type target_transform       mean_r2  median_r2       std_r2        min_r2   max_r2     mean_mae    median_mae      std_mae    mean_rmse   median_rmse     std_rmse     mean_mape  median_mape  folds  r2_win_count
                         ridge_alpha_100                         ridge_regression             none -2.125357e+00  -0.214716 5.559921e+00 -1.587940e+01 0.176137 2.744485e+05 215129.357924 2.386615e+05 3.319190e+05 273704.017143 2.395773e+05     30.670054     9.378062      8             1
                          ridge_alpha_10                         ridge_regression             none -2.242771e+00  -0.287031 5.714135e+00 -1.637727e+01 0.149691 2.813567e+05 220507.070010 2.388839e+05 3.401437e+05 281821.209128 2.429394e+05     31.148385     9.654315      8             0
                           ridge_alpha_1                         ridge_regression             none -2.804846e+00  -0.353867 7.195341e+00 -2.060523e+01 0.140047 2.985517e+05 223465.352976 2.739298e+05 3.572730e+05 286372.287289 2.784612e+05     34.441288     9.810730      8             0
            ridge_alpha_100_log1p_target                         ridge_regression            log1p -2.992399e+00  -0.218807 8.042438e+00 -2.289179e+01 0.177617 2.961773e+05 211436.898431 3.032350e+05 3.521719e+05 272124.254134 2.992043e+05     35.969025     9.182016      8             1
             ridge_alpha_10_log1p_target                         ridge_regression            log1p -3.180517e+00  -0.268504 8.415145e+00 -2.400171e+01 0.155611 3.043361e+05 217883.111348 3.090486e+05 3.612459e+05 279402.694601 3.064621e+05     36.846909     9.476675      8             0
              ridge_alpha_1_log1p_target                         ridge_regression            log1p -3.705630e+00  -0.295307 9.797612e+00 -2.794809e+01 0.142598 3.182319e+05 219447.906134 3.381802e+05 3.754892e+05 283113.747632 3.347029e+05     39.390608     9.566661      8             0
gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none -6.607467e+00  -0.130316 1.838355e+01 -5.210262e+01 0.112294 3.626969e+05 212530.279178 4.980932e+05 4.143642e+05 270657.929304 4.853996e+05     51.168949     9.330569      8             1
     gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none -7.175421e+00  -0.023749 2.020131e+01 -5.717041e+01 0.129057 3.689573e+05 208112.294363 5.264456e+05 4.164794e+05 259991.265023 5.141260e+05     53.217569     9.170961      8             1
     gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none -7.300733e+00  -0.023983 2.056754e+01 -5.820221e+01 0.119763 3.708804e+05 207037.692142 5.317291e+05 4.179163e+05 259277.291825 5.194732e+05     53.636100     9.121030      8             2
      gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none -7.695738e+00  -0.050398 2.165862e+01 -6.129782e+01 0.073499 3.792053e+05 206365.951334 5.462019e+05 4.240720e+05 257380.839799 5.344199e+05     54.980003     9.063692      8             2
                       linear_regression ordinary_least_squares_linear_regression             none -7.329181e+03  -0.406772 2.072922e+04 -5.863138e+04 0.147611 6.675679e+06 223975.347336 1.830024e+07 6.908992e+06 289856.205398 1.879047e+07   1443.831980     9.835317      8             0
          linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p -2.093096e+09  -0.331086 5.920168e+09 -1.674476e+10 0.147751 2.195161e+09 219810.560692 6.208284e+09 3.568233e+09 285822.361549 1.009175e+10 502488.129447     9.586040      8             0
```
