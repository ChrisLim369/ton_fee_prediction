# Model Evaluation Report

## Summary

- Best model: `gradient_boosted_stumps_200_lr_0_03`
- Best model R2: 0.098642
- Best model MAE: 159700.651 nanoton
- Best model RMSE: 214550.785 nanoton

## Interpretation

Low or negative R2 means next-hour fee prediction is still noisy relative to a test-period mean benchmark.
If the best model is nonlinear, treat the gain as useful but still validate it with rolling backtests before relying on it operationally.
The next priorities are more uniform historical backfill, uncertainty ranges, and outlier/log-target handling.

## Model Comparison

```text
          mae          rmse        r2     mape                               model_name                        model_type target_transform  alpha  train_rows  test_rows  max_depth  n_estimators  learning_rate  min_samples_leaf
159700.650766 214550.784640  0.098642 6.437749      gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none    0.0         580        145        1.0         200.0           0.03              20.0
160404.884066 215313.918451  0.092218 6.462835      gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none    0.0         580        145        1.0         100.0           0.05              20.0
164093.344725 219298.857285  0.058306 6.592632       gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none    0.0         580        145        1.0          50.0           0.05              20.0
166579.978407 220840.042193  0.045023 6.772587 gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none    0.0         580        145        3.0          50.0           0.10              20.0
163827.284177 220923.584041  0.044301 6.605740                          ridge_alpha_100                  ridge_regression             none  100.0         580        145        NaN           NaN            NaN               NaN
164807.393471 222533.622971  0.030320 6.621253             ridge_alpha_100_log1p_target                  ridge_regression            log1p  100.0         580        145        NaN           NaN            NaN               NaN
164383.748744 222993.357252  0.026309 6.629966                           ridge_alpha_10                  ridge_regression             none   10.0         580        145        NaN           NaN            NaN               NaN
165140.319288 224302.289762  0.014845 6.635486              ridge_alpha_10_log1p_target                  ridge_regression            log1p   10.0         580        145        NaN           NaN            NaN               NaN
165910.281528 225126.270798  0.007594 6.696388                            ridge_alpha_1                  ridge_regression             none    1.0         580        145        NaN           NaN            NaN               NaN
166435.719358 226230.772127 -0.002168 6.692761               ridge_alpha_1_log1p_target                  ridge_regression            log1p    1.0         580        145        NaN           NaN            NaN               NaN
```

## Rolling Backtest

Expanding-window backtest using recent 24-hour test folds. Higher mean R2 is better; lower mean MAE/RMSE is better.

```text
                              model_name                        model_type target_transform   mean_r2  median_r2   std_r2    min_r2   max_r2      mean_mae    median_mae      std_mae     mean_rmse   median_rmse     std_rmse  mean_mape  median_mape  folds  r2_win_count
     gradient_boosted_stumps_200_lr_0_03 gradient_boosted_regression_trees             none  0.015100   0.035543 0.108036 -0.133905 0.136730 155384.393468 137118.423326 38183.603408 202800.668305 178074.398499 52027.376962   6.312172     5.767891      8             2
     gradient_boosted_stumps_100_lr_0_05 gradient_boosted_regression_trees             none  0.011551   0.032758 0.104966 -0.141904 0.122647 155938.554244 136985.910124 38323.716193 203258.630595 177759.710052 52421.031801   6.328955     5.806811      8             2
gradient_boosted_trees_depth_3_50_lr_0_1 gradient_boosted_regression_trees             none -0.033355  -0.067952 0.122086 -0.187591 0.140626 161337.688698 136989.483022 40414.201152 207390.834341 181026.094562 51911.759921   6.601134     5.758501      8             2
      gradient_boosted_stumps_50_lr_0_05 gradient_boosted_regression_trees             none -0.035093  -0.024065 0.101999 -0.190631 0.073499 160509.724316 139929.221145 38770.868675 208151.508871 180225.349645 54012.448811   6.492816     6.019039      8             0
                         ridge_alpha_100                  ridge_regression             none -0.045769  -0.057519 0.160599 -0.232624 0.176113 161676.663780 139962.058663 39457.903228 208305.679887 178219.143049 53095.208705   6.592639     5.874382      8             0
            ridge_alpha_100_log1p_target                  ridge_regression            log1p -0.056747  -0.081027 0.176363 -0.244688 0.177590 162253.980466 142079.146981 40212.911577 209280.630289 180497.051449 53689.009850   6.588893     5.870126      8             2
                          ridge_alpha_10                  ridge_regression             none -0.059152  -0.083996 0.156593 -0.264987 0.149251 163084.543666 141602.209863 40444.736833 209807.841962 181139.971165 53858.588150   6.660590     5.889036      8             0
             ridge_alpha_10_log1p_target                  ridge_regression            log1p -0.067124  -0.087380 0.174757 -0.272146 0.155186 163049.260508 143863.097951 40871.673249 210401.702815 183059.561789 54129.821886   6.631393     5.945234      8             0
                           ridge_alpha_1                  ridge_regression             none -0.068631  -0.084609 0.154152 -0.277748 0.138224 164328.226815 143067.777815 40753.421084 210876.947784 183161.138646 54449.141472   6.716649     5.941228      8             0
              ridge_alpha_1_log1p_target                  ridge_regression            log1p -0.074537  -0.093119 0.174497 -0.283151 0.140839 163923.057996 145686.963897 41034.368574 211218.726550 185320.751092 54525.013818   6.673241     6.017116      8             0
```
