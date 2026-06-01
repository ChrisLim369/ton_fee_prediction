# Model Evaluation Report

## Summary

- Best model: `persistence`
- Selected by: rolling backtest naive fallback by mean MAE
- Best model R2: 0.453217
- Best model MAE: 61286.053 nanoton
- Best model RMSE: 107505.866 nanoton
- Best model directional accuracy: 0.000

## Interpretation

Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
          mae          rmse        r2      mape  directional_accuracy                               model_name                        model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
 61286.053015 107505.866202  0.453217 10.610819              0.000000                              persistence                             naive             none    0.0        1224        307        NaN           NaN            NaN               NaN
 70317.465990 114115.982615  0.383911 12.257176              0.648208                          ridge_alpha_100                  ridge_regression             none  100.0        1224        307        NaN           NaN            NaN               NaN
 65247.510411 115768.045276  0.365943 11.298600              0.661238                          rolling_mean_6h                             naive             none    0.0        1224        307        NaN           NaN            NaN               NaN
 71247.496868 123649.017596  0.276678 11.927097              0.644951                           ridge_alpha_10                  ridge_regression             none   10.0        1224        307        NaN           NaN            NaN               NaN
 75677.660331 130301.157633  0.196757 12.590030              0.651466                            ridge_alpha_1                  ridge_regression             none    1.0        1224        307        NaN           NaN            NaN               NaN
 72616.382962 131582.144350  0.180886 11.494293              0.651466             ridge_alpha_100_log1p_target                  ridge_regression            log1p  100.0        1224        307        NaN           NaN            NaN               NaN
 73509.163191 135622.861322  0.129805 11.337408              0.671010              ridge_alpha_10_log1p_target                  ridge_regression            log1p   10.0        1224        307        NaN           NaN            NaN               NaN
 76875.925189 144637.873864  0.010275 11.659789              0.664495               ridge_alpha_1_log1p_target                  ridge_regression            log1p    1.0        1224        307        NaN           NaN            NaN               NaN
110260.024421 162887.180323 -0.255233 20.533736              0.560261      gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none    0.0        1224        307        1.0         200.0           0.03              20.0
114564.614485 166679.794831 -0.314367 21.441333              0.557003      gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none    0.0        1224        307        1.0         100.0           0.05              20.0
 78974.803222 177769.425319 -0.495081 12.474752              0.657980 gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none    0.0        1224        307        3.0          50.0           0.10              20.0
116516.203359 194213.473838 -0.784470 19.493591              0.576547                       seasonal_naive_24h                             naive             none    0.0        1224        307        NaN           NaN            NaN               NaN
182320.837456 219982.044021 -1.289418 35.456050              0.501629       gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none    0.0        1224        307        1.0          50.0           0.05              20.0
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                        model_type target_transform   mean_r2  median_r2   std_r2     min_r2    max_r2      mean_mae   median_mae       std_mae     mean_rmse  median_rmse      std_rmse  mean_mape  median_mape  mean_directional_accuracy  median_directional_accuracy  folds  r2_win_count
gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none -0.069360  -0.059906 0.106016  -0.186314  0.088221  71494.024802 34042.537939  68836.341436 102888.720198 50384.565767 103025.709554  11.686958     7.418919                   0.677083                     0.687500      8             3
                         rolling_mean_6h                             naive             none -0.131474  -0.187535 0.245167  -0.392787  0.340038  71886.745006 40084.760259  66573.015364  98410.476690 55391.924354  93160.555603  12.088430     8.569364                   0.635417                     0.645833      8             1
                             persistence                             naive             none -0.259442  -0.219332 0.507990  -1.234484  0.417706  66105.237090 44448.672637  46569.334327  96297.288194 63047.263319  79127.803434  10.951094     9.347649                   0.000000                     0.000000      8             1
             ridge_alpha_10_log1p_target                  ridge_regression            log1p -0.545356  -0.215770 0.789346  -2.196870  0.085902  75788.486628 44697.955400  62240.467059 109090.617800 68217.646837  94303.258100  11.377340     8.964842                   0.666667                     0.666667      8             0
              ridge_alpha_1_log1p_target                  ridge_regression            log1p -0.600930  -0.301493 0.912448  -2.678350  0.101635  77941.603269 45293.535309  66424.357323 112446.338641 68246.673919  99534.817533  11.527193     8.724439                   0.677083                     0.645833      8             1
            ridge_alpha_100_log1p_target                  ridge_regression            log1p -0.656009  -0.168473 0.946301  -2.148137  0.069996  77330.082348 47204.547756  63308.505512 110254.724607 70558.505805  94070.960296  11.748833     9.621503                   0.645833                     0.666667      8             1
     gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none -0.777261  -0.908551 0.646751  -1.664311  0.478502  83776.103591 50417.659346  68784.786722 111542.266244 70602.524573  91822.999773  15.145427    10.793368                   0.609375                     0.604167      8             0
     gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none -0.911747  -0.945891 0.768800  -1.898234  0.472665  86026.279733 53323.019856  69016.702038 113494.134867 68664.344514  91424.299644  15.652534    11.623599                   0.614583                     0.645833      8             0
                          ridge_alpha_10                  ridge_regression             none -1.390065  -0.228832 2.674418  -7.237915  0.489222  70740.299097 55170.817015  46440.268186 106720.016955 76549.620345  77090.267913  11.796259    10.543714                   0.661458                     0.666667      8             1
                         ridge_alpha_100                  ridge_regression             none -1.414171  -0.383742 2.293409  -5.215612  0.484382  74289.000020 58409.025540  45932.103876 107060.487276 79125.268581  73985.027515  12.595624    11.313380                   0.614583                     0.583333      8             0
                           ridge_alpha_1                  ridge_regression             none -1.605265  -0.204839 3.209678  -9.018215  0.465995  71670.672816 56449.450618  46683.523746 109211.120864 76963.881933  78060.355822  11.846408    10.542544                   0.677083                     0.666667      8             0
                      seasonal_naive_24h                             naive             none -3.451645  -1.618927 5.249121 -16.095384 -0.131569 135275.071558 69425.846350 123639.089811 175406.663079 87864.987657 156530.073157  21.613591    13.447036                   0.609375                     0.604167      8             0
```
