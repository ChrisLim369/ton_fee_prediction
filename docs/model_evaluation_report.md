# Model Evaluation Report

## Summary

- Best model: `ridge_alpha_100`
- Baseline Linear Regression R2: -7930.919982
- Best model R2: 0.702835
- R2 change: 7931.622817
- MAE change: 39598359.009 nanoton
- RMSE change: 75478849.974 nanoton

## Interpretation

The best model improved over the plain linear-regression baseline on the chronological holdout split.
Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
         mae         rmse            r2         mape                               model_name                               model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
3.584633e+05 4.648374e+05  7.028354e-01 5.025214e+01                          ridge_alpha_100                         ridge_regression             none  100.0         672        168        NaN           NaN            NaN               NaN
3.786535e+05 4.864051e+05  6.746197e-01 5.226941e+01                           ridge_alpha_10                         ridge_regression             none   10.0         672        168        NaN           NaN            NaN               NaN
4.249530e+05 5.576669e+05  5.722947e-01 6.207049e+01                            ridge_alpha_1                         ridge_regression             none    1.0         672        168        NaN           NaN            NaN               NaN
4.243255e+05 5.693455e+05  5.541932e-01 6.555454e+01             ridge_alpha_100_log1p_target                         ridge_regression            log1p  100.0         672        168        NaN           NaN            NaN               NaN
4.472032e+05 5.945453e+05  5.138560e-01 6.840470e+01              ridge_alpha_10_log1p_target                         ridge_regression            log1p   10.0         672        168        NaN           NaN            NaN               NaN
4.891865e+05 6.639666e+05  3.937003e-01 7.726525e+01               ridge_alpha_1_log1p_target                         ridge_regression            log1p    1.0         672        168        NaN           NaN            NaN               NaN
6.163798e+05 9.026855e+05 -1.206445e-01 1.083795e+02 gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none    0.0         672        168        3.0          50.0           0.10              20.0
6.287186e+05 9.339056e+05 -1.995019e-01 1.122964e+02      gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none    0.0         672        168        1.0         200.0           0.03              20.0
6.328745e+05 9.408281e+05 -2.173503e-01 1.131756e+02      gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none    0.0         672        168        1.0         100.0           0.05              20.0
6.458385e+05 9.606917e+05 -2.692964e-01 1.156977e+02       gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none    0.0         672        168        1.0          50.0           0.05              20.0
3.995682e+07 7.594369e+07 -7.930920e+03 8.670902e+03                        linear_regression ordinary_least_squares_linear_regression             none    0.0         672        168        NaN           NaN            NaN               NaN
2.144365e+31 2.778770e+32 -1.061940e+53 4.252632e+27           linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p    0.0         672        168        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                               model_type target_transform       mean_r2  median_r2       std_r2        min_r2    max_r2     mean_mae    median_mae      std_mae    mean_rmse   median_rmse     std_rmse     mean_mape  median_mape  folds  r2_win_count
                         ridge_alpha_100                         ridge_regression             none -2.423553e+00  -0.240728 5.483881e+00 -1.588389e+01 -0.076530 2.669491e+05 215129.357924 2.445034e+05 3.219973e+05 273704.017143 2.484507e+05     32.205312    10.229145      8             1
                          ridge_alpha_10                         ridge_regression             none -2.637793e+00  -0.360603 5.635125e+00 -1.638123e+01 -0.137486 2.740945e+05 220507.070010 2.447051e+05 3.313288e+05 281821.209128 2.508037e+05     32.664996    10.666891      8             0
            ridge_alpha_100_log1p_target                         ridge_regression            log1p -3.169695e+00  -0.243240 7.980294e+00 -2.289784e+01 -0.036826 2.869745e+05 211436.898431 3.098162e+05 3.402308e+05 272124.254134 3.090348e+05     37.157787    10.096646      8             1
             ridge_alpha_10_log1p_target                         ridge_regression            log1p -3.414741e+00  -0.337728 8.336906e+00 -2.400745e+01 -0.080406 2.954357e+05 217883.111348 3.154995e+05 3.500607e+05 279402.694601 3.156428e+05     38.015417    10.393906      8             0
                           ridge_alpha_1                         ridge_regression             none -3.451991e+00  -0.435252 7.126398e+00 -2.060935e+01 -0.139897 2.934528e+05 223465.352976 2.777795e+05 3.514810e+05 286372.287289 2.831964e+05     36.424737    11.028091      8             0
              ridge_alpha_1_log1p_target                         ridge_regression            log1p -4.033261e+00  -0.423137 9.695885e+00 -2.795360e+01 -0.115648 3.105895e+05 219447.906134 3.435193e+05 3.656317e+05 283113.747632 3.424410e+05     40.823352    10.663451      8             0
gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none -1.399676e+01  -0.196215 2.572053e+01 -5.901345e+01  0.112294 3.966240e+05 216264.941035 4.899163e+05 4.446554e+05 294357.255636 4.768520e+05     61.678757     9.801909      8             1
     gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none -4.831483e+01  -0.084667 1.151541e+02 -3.289816e+02  0.025638 4.768078e+05 211362.782396 5.606080e+05 5.193892e+05 279217.479099 5.426204e+05     79.742959     9.782519      8             1
     gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none -5.104400e+01  -0.084436 1.224276e+02 -3.498220e+02  0.026995 4.826590e+05 211285.343698 5.694279e+05 5.246169e+05 277318.049561 5.515358e+05     81.013127     9.786096      8             2
      gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none -6.406551e+01  -0.092915 1.577594e+02 -4.508806e+02  0.014579 5.083069e+05 216968.758105 6.019906e+05 5.476820e+05 275224.409066 5.845507e+05     86.156688     9.845347      8             2
                       linear_regression ordinary_least_squares_linear_regression             none -7.326862e+03  -0.515602 2.072029e+04 -5.860696e+04 -0.128227 6.671535e+06 223975.347336 1.830212e+07 6.904263e+06 289856.205398 1.879259e+07   1447.242789    11.096369      8             0
          linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p -2.092189e+09  -0.477031 5.917605e+09 -1.673752e+10 -0.141501 2.195154e+09 219810.560692 6.208287e+09 3.568224e+09 285822.361549 1.009175e+10 502715.571334    10.711356      8             0
```
