from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_forward_fee_relation_sample() -> None:
    raw_path = ROOT / "raw_transactions.csv"
    if not raw_path.exists():
        pytest.skip("raw_transactions.csv is not available locally")

    df = pd.read_csv(raw_path, usecols=["total_fwd_fees", "out_msg_fwd_fee_sum"])
    if df.empty:
        pytest.skip("raw_transactions.csv has no rows")

    sample = df.sample(n=min(100, len(df)), random_state=42)
    total_fwd_fees = pd.to_numeric(sample["total_fwd_fees"], errors="coerce").fillna(0)
    out_msg_fwd_fee_sum = pd.to_numeric(sample["out_msg_fwd_fee_sum"], errors="coerce").fillna(0)

    equal_count = int((total_fwd_fees == out_msg_fwd_fee_sum).sum())
    both_nonzero = int(((total_fwd_fees > 0) & (out_msg_fwd_fee_sum > 0)).sum())
    total_only = int(((total_fwd_fees > 0) & (out_msg_fwd_fee_sum == 0)).sum())
    out_only = int(((total_fwd_fees == 0) & (out_msg_fwd_fee_sum > 0)).sum())

    print(
        "forward_fee_relation: "
        f"sample={len(sample)} equal={equal_count} both_nonzero={both_nonzero} "
        f"total_only={total_only} out_only={out_only}; "
        "conclusion=both fields often coexist, so summing them risks double-counting"
    )
