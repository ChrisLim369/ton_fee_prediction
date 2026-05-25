# Model Evaluation Report

## Summary

- Best model: `ridge_alpha_100`
- Best model R2: 0.107611
- Best model MAE: 637228.751 nanoton
- Best model RMSE: 700027.587 nanoton

## Interpretation

Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
         mae         rmse        r2       mape                               model_name                        model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
6.372288e+05 7.000276e+05  0.107611 117.124910                          ridge_alpha_100                  ridge_regression             none  100.0         750        188        NaN           NaN            NaN               NaN
7.042822e+05 7.746082e+05 -0.092668 129.530442                           ridge_alpha_10                  ridge_regression             none   10.0         750        188        NaN           NaN            NaN               NaN
7.716326e+05 8.483033e+05 -0.310468 143.796149             ridge_alpha_100_log1p_target                  ridge_regression            log1p  100.0         750        188        NaN           NaN            NaN               NaN
8.331608e+05 9.162370e+05 -0.528762 155.149545              ridge_alpha_10_log1p_target                  ridge_regression            log1p   10.0         750        188        NaN           NaN            NaN               NaN
8.608254e+05 9.502808e+05 -0.644478 158.910364                            ridge_alpha_1                  ridge_regression             none    1.0         750        188        NaN           NaN            NaN               NaN
9.601968e+05 1.058228e+06 -1.039307 178.813148               ridge_alpha_1_log1p_target                  ridge_regression            log1p    1.0         750        188        NaN           NaN            NaN               NaN
1.275690e+06 1.410547e+06 -2.623255 240.164923 gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none    0.0         750        188        3.0          50.0           0.10              20.0
1.330299e+06 1.470878e+06 -2.939830 250.517094      gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none    0.0         750        188        1.0         200.0           0.03              20.0
1.334272e+06 1.475512e+06 -2.964691 251.391958      gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none    0.0         750        188        1.0         100.0           0.05              20.0
1.354473e+06 1.499041e+06 -3.092143 255.620183       gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none    0.0         750        188        1.0          50.0           0.05              20.0
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                        model_type target_transform    mean_r2  median_r2     std_r2      min_r2    max_r2      mean_mae    median_mae       std_mae     mean_rmse   median_rmse      std_rmse  mean_mape  median_mape  folds  r2_win_count
            ridge_alpha_100_log1p_target                  ridge_regression            log1p  -4.153932  -1.673220   7.673022  -22.897841 -0.036826 239983.573789 127016.293696 329496.455170 274148.701095 157604.778514 337291.565121  41.960356    13.719589      8             2
                         ridge_alpha_100                  ridge_regression             none  -4.172492  -2.901693   5.142796  -15.883890 -0.076530 228998.046048 134129.099157 261458.355218 266494.803083 169001.258831 272891.348610  38.670586    18.038378      8             1
             ridge_alpha_10_log1p_target                  ridge_regression            log1p  -4.427675  -2.158049   8.009166  -24.007446 -0.080406 244928.561635 121156.936002 336622.668317 280821.688196 153700.780255 344951.646648  42.778178    13.564446      8             0
                          ridge_alpha_10                  ridge_regression             none  -4.993903  -3.787796   5.586547  -16.381233 -0.137486 236089.496717 133635.564910 262720.700523 278468.431138 169353.421184 274976.539783  39.720016    17.649250      8             0
              ridge_alpha_1_log1p_target                  ridge_regression            log1p  -5.019612  -2.224217   9.364005  -27.953599 -0.115648 256187.190399 117593.920208 365858.395766 292886.332102 154129.688825 372820.470806  45.315806    13.006838      8             1
                           ridge_alpha_1                  ridge_regression             none  -6.125872  -4.344606   7.179241  -20.609345 -0.186319 252984.724360 132364.191909 296535.954873 297771.111974 179220.146281 307997.576421  43.551238    18.438008      8             0
gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none -15.843405  -2.229651  24.803177  -59.100564  0.112294 351157.032635 156414.746470 512183.437352 386284.263114 199332.477639 505513.662447  66.888521    20.013903      8             2
     gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none -61.290538 -18.538946 111.307023 -329.076905 -0.001146 484823.884467 217669.901163 557540.245333 520554.423450 279289.664292 542026.277585  94.840585    33.691641      8             1
     gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none -65.627750 -19.620756 118.443830 -349.913225  0.007531 493964.061559 216186.169845 565153.361490 531005.315774 280999.143369 548458.078767  96.878228    33.863955      8             0
      gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none -94.794199 -35.830557 154.880314 -450.945010 -0.015173 567134.604047 276134.956248 575883.489622 603735.999019 358043.365340 558640.813184 111.578896    47.330125      8             1
```
