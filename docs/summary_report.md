# TON Transaction Fee Dataset Summary

## API Endpoint

- TON Center API v3 `GET /transactions`
- Base URL: `https://toncenter.com/api/v3`
- Authentication: optional `X-API-Key` header via `TONCENTER_API_KEY`.

## Collection Coverage

- Raw CSV: `raw_transactions.csv`
- Hourly CSV: `hourly_features.csv`
- Transactions after de-duplication: 3,612,967
- Date range UTC: 2026-03-29T06:00:07+00:00 to 2026-04-28T11:06:10+00:00
- Hourly rows: 726
- Hourly rows with next-hour target: 725

## Collection Metadata

- endpoint: https://toncenter.com/api/v3/transactions
- window_hours: 1
- limit: 1000
- max_pages_per_window: 1
- sort: asc
- workchain: 0
- request_count: 11
- windows_processed: 11
- windows_with_limit_hits: 11
- api_key_used: False
- new_rows_added: 10936
- status: success
- Limitation: at least one hourly window reached the request limit, so this run is a sampled transaction-level dataset rather than a complete chain-wide export for every hour.

## Fee Statistics

count    3.612967e+06
mean     2.344669e+06
std      3.752544e+06
min      0.000000e+00
50%      9.247940e+05
90%      5.605126e+06
95%      7.863590e+06
99%      1.313446e+07
max      5.704057e+08

## Missing Value Counts

balance_change            1460835
bounce                    1011153
action_success             366591
compute_success            331476
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
