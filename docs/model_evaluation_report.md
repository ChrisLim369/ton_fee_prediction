# Model Evaluation Report

## Summary

- Best model: `gradient_boosted_stumps_100_lr_0_05`
- Baseline Linear Regression R2: -0.347028
- Best model R2: 0.087714
- R2 change: 0.434742
- MAE change: 34452.980 nanoton
- RMSE change: 52341.370 nanoton

## Interpretation

The best model improved over the plain linear-regression baseline on the chronological holdout split.
Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
          mae          rmse        r2     mape                               model_name                               model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
185004.786259 243300.828367  0.087714 8.021877      gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none    0.0         633        159        1.0         100.0           0.05              20.0
184765.432073 243626.669826  0.085269 8.008443      gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none    0.0         633        159        1.0         200.0           0.03              20.0
188215.142441 243863.734525  0.083488 8.168163       gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none    0.0         633        159        1.0          50.0           0.05              20.0
199000.997849 259672.489191 -0.039192 8.596151 gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none    0.0         633        159        3.0          50.0           0.10              20.0
196599.032195 268009.086102 -0.106988 8.143102             ridge_alpha_100_log1p_target                         ridge_regression            log1p  100.0         633        159        NaN           NaN            NaN               NaN
198426.938154 270594.266868 -0.128447 8.228622                          ridge_alpha_100                         ridge_regression             none  100.0         633        159        NaN           NaN            NaN               NaN
205902.276776 278589.429028 -0.196116 8.508290              ridge_alpha_10_log1p_target                         ridge_regression            log1p   10.0         633        159        NaN           NaN            NaN               NaN
208823.438058 279723.655887 -0.205875 8.660404               ridge_alpha_1_log1p_target                         ridge_regression            log1p    1.0         633        159        NaN           NaN            NaN               NaN
208325.369855 282056.045978 -0.226068 8.627327                           ridge_alpha_10                         ridge_regression             none   10.0         633        159        NaN           NaN            NaN               NaN
211761.179749 283543.741888 -0.239036 8.808363                            ridge_alpha_1                         ridge_regression             none    1.0         633        159        NaN           NaN            NaN               NaN
213628.662022 287571.658625 -0.274489 8.822299           linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p    0.0         633        159        NaN           NaN            NaN               NaN
219457.765923 295642.198824 -0.347028 9.074961                        linear_regression ordinary_least_squares_linear_regression             none    0.0         633        159        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                               model_type target_transform   mean_r2  median_r2   std_r2    min_r2   max_r2      mean_mae    median_mae      std_mae     mean_rmse   median_rmse     std_rmse  mean_mape  median_mape  folds  r2_win_count
     gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none -0.031871  -0.021058 0.099577 -0.208988 0.119763 177259.288171 181091.842558 47338.481486 227270.294529 224841.869318 56348.789311   7.677231     7.920762      8             3
     gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none -0.037998  -0.023749 0.108249 -0.232310 0.129057 177263.463327 179713.872053 47669.078313 227890.305342 224707.561313 56629.768087   7.673886     7.902719      8             1
      gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none -0.040106  -0.033241 0.068886 -0.141439 0.073499 180448.888101 183272.799593 45656.350255 227959.942187 225991.585740 54530.902201   7.821264     8.061755      8             2
gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none -0.108545  -0.104867 0.163839 -0.390087 0.112294 181773.156287 175955.300885 50225.235925 235545.482664 223561.958205 61777.530877   7.795681     7.605841      8             1
            ridge_alpha_100_log1p_target                         ridge_regression            log1p -0.154933  -0.194816 0.174308 -0.410863 0.177617 184348.759646 178399.424782 49507.088720 240300.473901 229252.701011 63551.409930   7.797826     7.563884      8             1
                         ridge_alpha_100                         ridge_regression             none -0.157581  -0.176046 0.165664 -0.391714 0.176137 185189.670177 182013.140077 50448.475964 241012.845996 233732.641188 64936.200396   7.872116     7.764750      8             0
             ridge_alpha_10_log1p_target                         ridge_regression            log1p -0.209654  -0.220423 0.188911 -0.464113 0.155611 190235.730819 183444.381162 55103.850307 246685.761512 235922.868932 68822.010617   8.036852     7.791019      8             0
                          ridge_alpha_10                         ridge_regression             none -0.217771  -0.207049 0.184269 -0.444011 0.149691 191764.268644 187347.745002 56259.167731 247969.950311 242039.953482 70502.190696   8.144781     8.005827      8             0
              ridge_alpha_1_log1p_target                         ridge_regression            log1p -0.246289  -0.248455 0.206864 -0.482214 0.142598 193797.183300 184750.887506 59187.519110 250803.374342 240488.431838 72206.965241   8.190241     7.858643      8             0
                           ridge_alpha_1                         ridge_regression             none -0.255920  -0.255219 0.205188 -0.478611 0.140047 196287.639737 190169.142214 60543.293558 252224.442120 247837.936366 73941.604026   8.343528     8.144818      8             0
          linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p -0.269428  -0.254563 0.228387 -0.536585 0.147751 194520.209789 186068.801558 60628.062254 253406.395071 242175.866010 75198.083789   8.206410     7.917839      8             0
                       linear_regression ordinary_least_squares_linear_regression             none -0.285371  -0.264685 0.235295 -0.528136 0.147611 197497.933899 193123.062148 62931.722806 255520.778499 249900.161833 77852.066982   8.375905     8.277470      8             0
```
