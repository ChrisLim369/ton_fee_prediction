# Horizon-Aware Forecast Experiment

This measurement compares three read-only forecast candidates with recursive 24-hour rolling-origin evaluation. It does not write deployment forecasts, models, predictions, or mirrored data.

## Method

- Input: `hourly_features.csv`, sorted by `hour`.
- Fixed chronological split: holdout starts at row 1224.
- Ridge training rows after capped-target exclusion: 506.
- Ridge is fit once before holdout on clean-target rows only.
- Each origin passes only `df.iloc[:t+1]` into `recursive_forecast()`; origin-future rows are used only as actuals.
- Regime split: clean origins before 2026-05-26; recent/capped origins from that date onward.

## Per-Horizon MAE

| Horizon | Persistence MAE | Rolling mean 6h MAE | Ridge clean MAE | Rolling skill | Ridge skill | Winner |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 63463.478 | 68465.678 | 66315.030 | -0.078820 | -0.044932 | persistence |
| 2 | 75333.227 | 75132.623 | 132831.175 | 0.002663 | -0.763248 | rolling_mean_6h |
| 3 | 83602.738 | 80542.828 | 162770.551 | 0.036601 | -0.946952 | rolling_mean_6h |
| 4 | 90832.650 | 83973.455 | 175297.510 | 0.075515 | -0.929895 | rolling_mean_6h |
| 5 | 96660.408 | 85680.377 | 180116.383 | 0.113594 | -0.863394 | rolling_mean_6h |
| 6 | 97656.309 | 86808.708 | 183470.762 | 0.111079 | -0.878739 | rolling_mean_6h |
| 7 | 98345.066 | 86137.522 | 185728.001 | 0.124130 | -0.888534 | rolling_mean_6h |
| 8 | 94774.307 | 85396.375 | 188442.645 | 0.098950 | -0.988331 | rolling_mean_6h |
| 9 | 95911.212 | 86519.070 | 190128.840 | 0.097925 | -0.982342 | rolling_mean_6h |
| 10 | 96971.493 | 89681.103 | 191479.977 | 0.075181 | -0.974601 | rolling_mean_6h |
| 11 | 97955.214 | 92542.585 | 192607.364 | 0.055256 | -0.966280 | rolling_mean_6h |
| 12 | 102085.453 | 95169.709 | 193958.386 | 0.067745 | -0.899961 | rolling_mean_6h |
| 13 | 104025.992 | 97070.724 | 195261.538 | 0.066861 | -0.877046 | rolling_mean_6h |
| 14 | 107842.568 | 97121.734 | 193787.869 | 0.099412 | -0.796952 | rolling_mean_6h |
| 15 | 107898.916 | 97290.073 | 193039.544 | 0.098322 | -0.789078 | rolling_mean_6h |
| 16 | 109877.094 | 99151.559 | 193005.249 | 0.097614 | -0.756556 | rolling_mean_6h |
| 17 | 111470.948 | 100432.166 | 193704.031 | 0.099028 | -0.737709 | rolling_mean_6h |
| 18 | 111353.728 | 99593.352 | 194330.142 | 0.105613 | -0.745161 | rolling_mean_6h |
| 19 | 110738.890 | 100045.661 | 194914.066 | 0.096563 | -0.760123 | rolling_mean_6h |
| 20 | 110407.508 | 100212.671 | 195592.398 | 0.092338 | -0.771550 | rolling_mean_6h |
| 21 | 108397.410 | 101103.434 | 196315.183 | 0.067289 | -0.811069 | rolling_mean_6h |
| 22 | 111358.075 | 104214.820 | 196743.564 | 0.064147 | -0.766765 | rolling_mean_6h |
| 23 | 112801.772 | 107890.722 | 197532.477 | 0.043537 | -0.751147 | rolling_mean_6h |
| 24 | 116709.879 | 110787.966 | 198697.583 | 0.050740 | -0.702492 | rolling_mean_6h |

## 24h Average MAE

| Model | 24h average MAE | Skill vs persistence |
| --- | --- | --- |
| persistence | 100686.431 | 0.000000 |
| rolling_mean_6h | 92956.872 | 0.076769 |
| ridge_alpha_100_log1p_target | 182752.928 | -0.815070 |

## Regime Transfer

| Regime | Persistence MAE | Rolling mean 6h MAE | Ridge clean MAE |
| --- | --- | --- | --- |
| clean | 64944.022 | 57359.327 | 182728.049 |
| recent_capped | 148147.661 | 140225.742 | 182785.964 |

- Evaluated clean origins per candidate: 162
- Evaluated recent/capped origins per candidate: 122

## Recommendation

- Per-horizon winner synthesis: h1=persistence, h2-h24=rolling_mean_6h
- Persistence replacement threshold: a non-persistence candidate should win across many horizons and beat persistence in both clean and recent/capped regimes.
- Replacement candidate: rolling_mean_6h

## Conclusion

rolling_mean_6h meets the measurement threshold for a persistence replacement candidate; the horizon-aware synthesis is h1=persistence, h2-h24=rolling_mean_6h.
