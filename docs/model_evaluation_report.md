# Model Evaluation Report

## Summary

- Best model: `rolling_mean_6h`
- Selected by: rolling backtest mean R2 (tie-break median RMSE)
- Best model R2: 0.135928
- Best model MAE: 45741.041 nanoton
- Best model RMSE: 67061.841 nanoton
- Best model directional accuracy: 0.625

## Interpretation

Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
          mae          rmse        r2      mape  directional_accuracy                               model_name                        model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
 44335.780572  65017.690282  0.187802  8.862022              0.000000                              persistence                             naive             none    0.0        1119        280        NaN           NaN            NaN               NaN
 45741.040857  67061.840924  0.135928  9.152077              0.625000                          rolling_mean_6h                             naive             none    0.0        1119        280        NaN           NaN            NaN               NaN
 62641.236394  88070.714093 -0.490260 12.418918              0.592857                       seasonal_naive_24h                             naive             none    0.0        1119        280        NaN           NaN            NaN               NaN
 70405.747378  96358.569918 -0.783938 14.759164              0.603571              ridge_alpha_10_log1p_target                  ridge_regression            log1p   10.0        1119        280        NaN           NaN            NaN               NaN
 69724.683138  97999.202920 -0.845203 14.490853              0.625000               ridge_alpha_1_log1p_target                  ridge_regression            log1p    1.0        1119        280        NaN           NaN            NaN               NaN
 81269.804832 106006.328345 -1.159049 17.474398              0.557143             ridge_alpha_100_log1p_target                  ridge_regression            log1p  100.0        1119        280        NaN           NaN            NaN               NaN
 90805.657328 108032.717243 -1.242382 19.245136              0.503571      gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none    0.0        1119        280        1.0         200.0           0.03              20.0
 87641.793552 110309.107765 -1.337877 18.407114              0.585714 gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none    0.0        1119        280        3.0          50.0           0.10              20.0
 97448.332370 112927.402799 -1.450178 20.700792              0.489286      gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none    0.0        1119        280        1.0         100.0           0.05              20.0
 85144.901614 118737.346295 -1.708780 17.817999              0.567857                           ridge_alpha_10                  ridge_regression             none   10.0        1119        280        NaN           NaN            NaN               NaN
 85746.491359 121882.153165 -1.854166 17.805679              0.614286                            ridge_alpha_1                  ridge_regression             none    1.0        1119        280        NaN           NaN            NaN               NaN
102009.203225 134903.564546 -2.496599 21.998977              0.528571                          ridge_alpha_100                  ridge_regression             none  100.0        1119        280        NaN           NaN            NaN               NaN
190984.332174 200513.245510 -6.724762 40.410202              0.450000       gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none    0.0        1119        280        1.0          50.0           0.05              20.0
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                        model_type target_transform   mean_r2  median_r2   std_r2     min_r2    max_r2     mean_mae   median_mae      std_mae     mean_rmse  median_rmse     std_rmse  mean_mape  median_mape  mean_directional_accuracy  median_directional_accuracy  folds  r2_win_count
                         rolling_mean_6h                             naive             none -0.236161  -0.284467 0.200723  -0.478079  0.094668 46730.327487 37165.762413 28647.632665  61974.381064 49229.786985 36836.894878   8.895618     6.889680                   0.656250                     0.666667      8             2
gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none -0.256217  -0.246952 0.294357  -0.673482  0.105732 47920.513046 38101.936922 26870.765613  63330.729894 47715.008737 42714.677355   9.350303     8.199096                   0.640625                     0.645833      8             1
              ridge_alpha_1_log1p_target                  ridge_regression            log1p -0.534806  -0.565968 0.518746  -1.201731  0.128848 49380.248338 41616.479996 19981.956395  64386.576058 53275.577224 29109.541791   9.357413     8.455468                   0.666667                     0.645833      8             0
                             persistence                             naive             none -0.548658  -0.447871 0.632632  -1.822416  0.194235 46294.379705 40344.470267 16675.978458  64437.710005 59219.165416 27453.080641   8.964016     8.420430                   0.000000                     0.000000      8             1
             ridge_alpha_10_log1p_target                  ridge_regression            log1p -0.558273  -0.525082 0.552930  -1.311923  0.153824 49469.214681 42555.646487 18312.388895  64295.733055 55531.058643 28064.466539   9.459936     8.687343                   0.656250                     0.625000      8             0
            ridge_alpha_100_log1p_target                  ridge_regression            log1p -0.671836  -0.302603 0.959852  -2.141740  0.190470 49300.579129 45156.789873 15879.325761  62924.571400 56693.830451 24285.928824   9.706555     9.757806                   0.614583                     0.541667      8             2
                          ridge_alpha_10                  ridge_regression             none -1.106235  -0.791558 1.198509  -3.546776  0.055485 56485.732367 47743.808674 23002.042409  72351.731719 66549.651542 31088.282793  10.847082     9.597367                   0.619792                     0.625000      8             0
                           ridge_alpha_1                  ridge_regression             none -1.157860  -1.032225 1.096554  -3.266907 -0.067938 58883.474410 48931.679664 27004.933663  74864.417340 67874.173001 34656.778888  11.220560     9.805956                   0.630208                     0.645833      8             0
                         ridge_alpha_100                  ridge_regression             none -1.330680  -0.731192 1.788288  -4.915149  0.170705 57157.939205 50675.566950 17240.182961  69520.164348 63654.875128 22693.745975  11.434912    10.293049                   0.598958                     0.562500      8             1
                      seasonal_naive_24h                             naive             none -2.285555  -2.144867 2.593075  -7.716171  0.297746 66990.994865 62504.887620 32076.147910  87002.358101 81581.511065 42247.944667  12.740024    12.538391                   0.578125                     0.583333      8             1
     gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none -3.421163  -0.955329 5.529512 -16.752479 -0.368085 85250.107228 59105.908922 68813.880253 104121.461446 72760.260779 78300.665723  16.538527    12.315896                   0.541667                     0.541667      8             0
     gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none -3.988036  -1.517335 5.770342 -17.716339 -0.570685 91809.751363 68779.095337 69175.565439 110542.674495 80931.773993 79281.743789  17.975723    14.460699                   0.526042                     0.500000      8             0
```
