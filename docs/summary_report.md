# TON Transaction Fee Dataset Summary

## API Endpoint

- TON Center API v3 `GET /transactions`
- Base URL: `https://toncenter.com/api/v3`
- Authentication: optional `X-API-Key` header via `TONCENTER_API_KEY`.

## Collection Coverage

- Raw CSV: `raw_transactions.csv`
- Hourly CSV: `hourly_features.csv`
- Transactions after de-duplication: 13,330,591
- Date range UTC: 2026-03-29T06:00:07+00:00 to 2026-05-31T05:00:00+00:00
- Hourly rows: 1,512
- Hourly rows with next-hour target: 1,511

## Collection Metadata

- endpoint: https://toncenter.com/api/v3/transactions
- window_hours: 1
- limit: 1000
- max_pages_per_window: 1
- sort: asc
- workchain: 0
- request_count: 1124
- windows_processed: 113
- windows_with_limit_hits: 1123
- api_key_used: True
- new_rows_added: 1123986
- status: success
- Limitation: at least one hourly window reached the request limit, so this run is a sampled transaction-level dataset rather than a complete chain-wide export for every hour.

## Fee Statistics

count    1.333059e+07
mean     1.211841e+06
std      2.751497e+06
min      0.000000e+00
50%      4.563580e+05
90%      3.359732e+06
95%      5.074266e+06
99%      9.352376e+06
max      1.490383e+09

## Missing Value Counts

balance_change            5971596
bounce                    3415133
action_success            1197841
compute_success           1087542
hash                            0
now                             0
in_msg_value                    0
transaction_value               0
destroyed                       0
account_type                    0
transaction_type                0
aborted                         0
msg_size_cells                  0
msg_size_bits                   0
tot_actions                     0
msgs_created                    0
vm_steps                        0
out_msg_count                   0
out_msg_fwd_fee_sum             0
in_msg_fwd_fee                  0
in_msg_import_fee               0
total_fwd_fees                  0
total_action_fees               0
storage_fees_due                0
storage_fees_collected          0
compute_gas_fees                0
compute_gas_used                0
total_fees                      0
mc_block_seqno                  0
lt                              0
account                         0
out_msg_value_sum               0

## Modeling Notes

- The target column is `target_next_hour_avg_fee`.
- Lag and rolling features are shifted so they only use prior-hour fee information.
- UTC is used for primary time features. Convert `hour` to Asia/Seoul for KST dashboards when needed.
- If collection hit API page limits, treat `tx_count` and `unique_accounts` as sample counts, not total network counts.
