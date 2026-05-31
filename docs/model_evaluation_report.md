# Model Evaluation Report

## Summary

- Best model: `rolling_mean_6h`
- Selected by: rolling backtest mean R2 (tie-break median RMSE)
- Best model R2: 0.366183
- Best model MAE: 66791.062 nanoton
- Best model RMSE: 116844.300 nanoton
- Best model directional accuracy: 0.653

## Interpretation

Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
          mae          rmse        r2      mape  directional_accuracy                               model_name                        model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
 62684.598604 109059.947754  0.447822 10.897225              0.000000                              persistence                             naive             none    0.0        1208        303        NaN           NaN            NaN               NaN
 74063.163097 116118.772529  0.374030 13.117551              0.623762                          ridge_alpha_100                  ridge_regression             none  100.0        1208        303        NaN           NaN            NaN               NaN
 66791.061857 116844.299879  0.366183 11.617105              0.653465                          rolling_mean_6h                             naive             none    0.0        1208        303        NaN           NaN            NaN               NaN
 73356.866842 124773.325577  0.277243 12.471464              0.643564                           ridge_alpha_10                  ridge_regression             none   10.0        1208        303        NaN           NaN            NaN               NaN
 64404.124106 129001.691531  0.227427 11.426601              0.633663 gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none    0.0        1208        303        3.0          50.0           0.10              20.0
 76794.482690 131056.401357  0.202621 12.959000              0.646865                            ridge_alpha_1                  ridge_regression             none    1.0        1208        303        NaN           NaN            NaN               NaN
 74846.304173 132041.577627  0.190587 12.034219              0.613861             ridge_alpha_100_log1p_target                  ridge_regression            log1p  100.0        1208        303        NaN           NaN            NaN               NaN
 74910.459049 135596.547790  0.146417 11.722001              0.660066              ridge_alpha_10_log1p_target                  ridge_regression            log1p   10.0        1208        303        NaN           NaN            NaN               NaN
 77818.035046 144133.351718  0.035555 11.952054              0.660066               ridge_alpha_1_log1p_target                  ridge_regression            log1p    1.0        1208        303        NaN           NaN            NaN               NaN
133079.180408 191841.337893 -0.708571 24.878456              0.544554      gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none    0.0        1208        303        1.0         200.0           0.03              20.0
116510.301663 195043.085991 -0.766077 19.436074              0.580858                       seasonal_naive_24h                             naive             none    0.0        1208        303        NaN           NaN            NaN               NaN
136387.605241 195530.295479 -0.774911 25.568753              0.554455      gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none    0.0        1208        303        1.0         100.0           0.05              20.0
200867.833752 249105.467678 -1.880813 38.691931              0.485149       gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none    0.0        1208        303        1.0          50.0           0.05              20.0
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                        model_type target_transform   mean_r2  median_r2   std_r2     min_r2    max_r2      mean_mae   median_mae       std_mae     mean_rmse  median_rmse      std_rmse  mean_mape  median_mape  mean_directional_accuracy  median_directional_accuracy  folds  r2_win_count
                         rolling_mean_6h                             naive             none -0.127794  -0.172815 0.243293  -0.392787  0.340038  69903.103898 36743.442647  67847.032091  95938.835819 49801.129730  94780.347404  11.737448     7.721242                   0.661458                     0.666667      8             2
gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none -0.164573  -0.137777 0.222417  -0.673482  0.015693  71121.812144 32553.687307  69064.781122 102101.649368 47236.282445 103550.722807  11.680346     7.392470                   0.682292                     0.687500      8             3
                             persistence                             naive             none -0.473757  -0.379359 0.742472  -1.822416  0.417706  66175.329558 44729.042508  46522.161447  96388.447774 63411.901640  79067.241508  11.029984     9.663210                   0.000000                     0.000000      8             1
             ridge_alpha_10_log1p_target                  ridge_regression            log1p -0.720084  -0.310188 0.784344  -2.196870  0.039135  75626.170814 44048.692146  62352.640409 109152.631546 68465.701821  94255.554455  11.441119     9.105791                   0.661458                     0.666667      8             0
              ridge_alpha_1_log1p_target                  ridge_regression            log1p -0.763851  -0.483661 0.885030  -2.678350  0.021195  77706.559955 44353.362051  66590.004499 112418.980943 68246.673919  99556.024491  11.572427     8.905375                   0.671875                     0.645833      8             0
            ridge_alpha_100_log1p_target                  ridge_regression            log1p -0.895392  -0.421254 1.004639  -2.148137  0.069996  77753.734956 48237.594955  63044.989001 110712.891638 71053.995317  93733.419844  11.941889     9.836078                   0.635417                     0.666667      8             1
     gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none -1.016021  -0.955329 0.967852  -2.801681  0.478502  83832.845919 50644.628661  68752.126776 110735.094384 67373.837132  92314.318852  15.299204    10.976243                   0.578125                     0.583333      8             0
     gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none -1.328706  -1.217861 1.400295  -4.225316  0.472665  87433.870262 58745.298578  68272.437446 113959.759755 70526.844064  91152.849131  16.086697    13.064152                   0.583333                     0.604167      8             0
                          ridge_alpha_10                  ridge_regression             none -1.578416  -0.351846 2.619913  -7.237915  0.489222  70320.911205 55170.817015  46740.316118 106652.899622 76549.620345  77147.993436  11.786823    10.543714                   0.656250                     0.666667      8             1
                         ridge_alpha_100                  ridge_regression             none -1.671734  -0.731192 2.256522  -5.215612  0.484382  74345.493859 58409.025540  45892.440787 107325.801406 79125.268581  73765.434288  12.694103    11.313380                   0.609375                     0.562500      8             0
                           ridge_alpha_1                  ridge_regression             none -1.768968  -0.440530 3.157063  -9.018215  0.465995  71005.126331 55940.515565  47148.704868 108783.460076 76963.881933  78435.482058  11.782315    10.542544                   0.671875                     0.666667      8             0
                      seasonal_naive_24h                             naive             none -3.968051  -1.618927 5.462965 -16.095384 -0.131569 133544.831875 62504.887620 124618.702019 173835.793931 81581.511065 157435.734059  21.386430    12.538391                   0.604167                     0.604167      8             0
```
