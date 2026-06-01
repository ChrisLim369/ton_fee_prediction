# Capped Target Exclusion Experiment

This measurement runs `src/train_model.py` twice against committed `hourly_features.csv`: once with all rows, and once with `--exclude-capped-targets`. All training outputs are redirected to temporary directories and deleted after extracting metrics.

## Results

| Run | Selected model | Selected by | Rolling MAE selected | Rolling MAE persistence | Skill vs persistence | Rolling mean R2 | Holdout MAE | Holdout R2 | Rows before | Rows after | Rows excluded |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | persistence | rolling backtest naive fallback by mean MAE | 66105.237 | 66105.237 | 0.000000 | -0.259442 | 61286.053 | 0.453217 | 1532 | 1532 | 0 |
| excluded | ridge_alpha_100_log1p_target | rolling backtest MAE skill vs persistence | 40803.802 | 44388.783 | 0.080763 | 0.013098 | 31753.129 | 0.257835 | 1532 | 699 | 833 |

## Methodology Caveat

`--exclude-capped-targets` drops rows before the chronological split, so the two runs do not use identical test sets. Cross-run absolute MAE is therefore not a clean apples-to-apples measure. Interpret the result by checking whether the selected model changes, whether each run's selected model has positive `skill_vs_persistence`, and the direction and rough size of rolling mean MAE.

## Data-Driven Recommendation

Rule: if exclusion changes selection from a naive model to a feature model, gives the excluded selected model positive skill versus persistence, or improves selected rolling mean MAE by about 5% or more, treat exclusion as useful. Otherwise treat the effect as minimal and avoid API recollection.

- Selection changed naive to feature model: True
- Excluded selected-model skill_vs_persistence > 0: True
- Selected rolling mean MAE change vs baseline: 38.27%
- Recommendation branch: helpful
- Recommendation: Capped-target exclusion appears helpful. Consider adopting `--exclude-capped-targets` for Wave 3-2 retraining, and only consider API backfill if a remaining data gap needs it.

## Conclusion

HELPFUL: baseline selected `persistence` with skill_vs_persistence 0.000000; excluded selected `ridge_alpha_100_log1p_target` with skill_vs_persistence 0.080763 after excluding 833 capped-target rows.
