# Model Evaluation Report

## Summary

- Best model: `gradient_boosted_stumps_100_lr_0_05`
- Baseline Linear Regression R2: -0.193755
- Best model R2: 0.112600
- R2 change: 0.306356
- MAE change: 23402.620 nanoton
- RMSE change: 37221.497 nanoton

## Interpretation

The best model improved over the plain linear-regression baseline on the chronological holdout split.
Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
          mae          rmse        r2     mape                               model_name                               model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
177796.977198 232867.463991  0.112600 7.752266      gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none    0.0         615        154        1.0         100.0           0.05              20.0
177353.100488 233186.330564  0.110168 7.731095      gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none    0.0         615        154        1.0         200.0           0.03              20.0
182823.152570 234861.532966  0.097337 7.973385       gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none    0.0         615        154        1.0          50.0           0.05              20.0
185437.478525 245490.210166  0.013789 8.013467 gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none    0.0         615        154        3.0          50.0           0.10              20.0
184824.261374 249449.147915 -0.018277 7.729094             ridge_alpha_100_log1p_target                         ridge_regression            log1p  100.0         615        154        NaN           NaN            NaN               NaN
186203.054034 252074.079038 -0.039820 7.796816                          ridge_alpha_100                         ridge_regression             none  100.0         615        154        NaN           NaN            NaN               NaN
191670.350269 257130.100108 -0.081951 8.001980              ridge_alpha_10_log1p_target                         ridge_regression            log1p   10.0         615        154        NaN           NaN            NaN               NaN
193983.538021 257628.263097 -0.086147 8.125497               ridge_alpha_1_log1p_target                         ridge_regression            log1p    1.0         615        154        NaN           NaN            NaN               NaN
193960.674581 260712.118107 -0.112306 8.116680                           ridge_alpha_10                         ridge_regression             none   10.0         615        154        NaN           NaN            NaN               NaN
196676.648600 261637.833910 -0.120219 8.262227                            ridge_alpha_1                         ridge_regression             none    1.0         615        154        NaN           NaN            NaN               NaN
196384.694311 262738.426183 -0.129663 8.190621           linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p    0.0         615        154        NaN           NaN            NaN               NaN
201199.596713 270088.961356 -0.193755 8.401089                        linear_regression ordinary_least_squares_linear_regression             none    0.0         615        154        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                               model_type target_transform   mean_r2  median_r2   std_r2    min_r2   max_r2      mean_mae    median_mae      std_mae     mean_rmse   median_rmse     std_rmse  mean_mape  median_mape  folds  r2_win_count
     gradient_boosted_stumps_100_lr_0_05        gradient_boosted_regression_trees             none  0.009874   0.012890 0.083408 -0.113374 0.124974 167231.430514 148218.098874 48428.935761 213994.557873 189190.440112 58960.775651   7.283903     6.501288      8             3
     gradient_boosted_stumps_200_lr_0_03        gradient_boosted_regression_trees             none  0.008212   0.006250 0.090979 -0.122981 0.137371 166685.689812 146937.773784 48700.899370 214157.960827 189122.894891 59233.532496   7.257303     6.435537      8             1
      gradient_boosted_stumps_50_lr_0_05        gradient_boosted_regression_trees             none -0.013708  -0.015181 0.064853 -0.100224 0.073499 172210.025086 155035.077172 47400.230594 216230.849783 192689.389233 57562.999659   7.505500     6.840223      8             1
gradient_boosted_trees_depth_3_50_lr_0_1        gradient_boosted_regression_trees             none -0.041990  -0.090323 0.139464 -0.228523 0.142355 170174.462429 139518.070899 50970.821529 219689.430917 185207.955335 64127.144131   7.356068     5.930074      8             1
            ridge_alpha_100_log1p_target                         ridge_regression            log1p -0.084545  -0.142154 0.169833 -0.247471 0.177617 174444.140917 146386.418580 52329.353486 224068.394172 189718.737228 66998.012575   7.433594     6.334522      8             2
                         ridge_alpha_100                         ridge_regression             none -0.090560  -0.136194 0.165867 -0.266718 0.176137 175089.404514 148217.285136 52978.099786 225112.282051 190193.519299 68641.980046   7.498215     6.447498      8             0
             ridge_alpha_10_log1p_target                         ridge_regression            log1p -0.136220  -0.189417 0.190045 -0.345260 0.155611 179240.172299 148057.195082 58139.167182 230115.247613 193400.930991 72668.451871   7.626278     6.401342      8             0
                          ridge_alpha_10                         ridge_regression             none -0.148613  -0.177919 0.190932 -0.380466 0.149691 181096.500768 151184.300567 59177.282332 231807.360301 194430.650942 74632.252349   7.748168     6.591215      8             0
              ridge_alpha_1_log1p_target                         ridge_regression            log1p -0.174330  -0.197707 0.214301 -0.482214 0.142598 182836.324509 149952.273448 62423.888142 234346.565945 196497.648747 76410.036071   7.782066     6.445919      8             0
                           ridge_alpha_1                         ridge_regression             none -0.189326  -0.199254 0.214736 -0.478611 0.140047 185532.244224 152959.505669 63750.171666 236262.124182 197409.578201 78238.711227   7.943803     6.673417      8             0
          linear_regression_log1p_target ordinary_least_squares_linear_regression            log1p -0.193212  -0.197410 0.233006 -0.536585 0.147751 183472.365774 149783.566346 63826.774926 236520.001919 197797.850858 79276.462611   7.791553     6.433904      8             0
                       linear_regression ordinary_least_squares_linear_regression             none -0.211879  -0.217795 0.241465 -0.528136 0.147611 186466.837280 154325.925009 66139.903875 238871.477193 199049.458041 82017.009639   7.960283     6.723983      8             0
```
