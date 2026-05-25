import json
from pathlib import Path

from src.ton_pipeline import RAW_COLUMNS, flatten_transaction

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_flatten_transaction_normal_schema_and_types() -> None:
    row = flatten_transaction(load_fixture("tx_normal.json"))

    assert set(row) == set(RAW_COLUMNS)
    assert isinstance(row["total_fees"], int)
    assert isinstance(row["compute_gas_fees"], int)
    assert isinstance(row["lt"], int)
    assert isinstance(row["hash"], str)
    assert isinstance(row["account"], str)
    assert isinstance(row["transaction_type"], str)
    assert row["out_msg_fwd_fee_sum"] == 143
    assert row["transaction_value"] == 1_500_000_000


def test_flatten_transaction_without_in_msg_defaults_inbound_fields() -> None:
    row = flatten_transaction(load_fixture("tx_no_in_msg.json"))

    assert row["in_msg_import_fee"] == 0
    assert row["in_msg_fwd_fee"] == 0
    assert row["in_msg_value"] == 0
    assert row["bounce"] is None


def test_flatten_transaction_without_action_defaults_action_fields() -> None:
    row = flatten_transaction(load_fixture("tx_no_action.json"))

    assert row["total_action_fees"] == 0
    assert row["total_fwd_fees"] == 0
    assert row["msgs_created"] == 0
    assert row["tot_actions"] == 0
    assert row["action_success"] is None


def test_flatten_transaction_without_compute_defaults_compute_fields() -> None:
    row = flatten_transaction(load_fixture("tx_missing_compute.json"))

    assert row["compute_gas_used"] == 0
    assert row["compute_gas_fees"] == 0
    assert row["vm_steps"] == 0
    assert row["compute_success"] is None
