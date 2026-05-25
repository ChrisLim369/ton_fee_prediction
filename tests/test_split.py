import numpy as np
import pandas as pd
import pytest

from src.features import prepare_model_matrix
from src.models.base import split_model_data
from src.schema import MODEL_FEATURE_COLUMNS


def synthetic_hourly(days: int = 60) -> pd.DataFrame:
    rows = days * 24
    hours = pd.date_range("2024-01-01T00:00:00Z", periods=rows, freq="h")
    df = pd.DataFrame({"hour": hours.strftime("%Y-%m-%dT%H:%M:%SZ")})
    for index, column in enumerate(MODEL_FEATURE_COLUMNS, start=1):
        df[column] = np.arange(rows, dtype=float) + index
    df["target_next_hour_avg_fee"] = np.arange(rows, dtype=float) + 10_000
    df.loc[0, MODEL_FEATURE_COLUMNS[0]] = np.nan
    return df


def test_split_model_data_preserves_chronological_holdout_and_train_stats() -> None:
    df = synthetic_hourly()
    feature_columns = MODEL_FEATURE_COLUMNS[:5]
    usable_rows = int(df[feature_columns].notna().any(axis=1).sum())

    split = split_model_data(
        hourly_df=df,
        feature_columns=feature_columns,
        target_column="target_next_hour_avg_fee",
        test_fraction=0.2,
    )
    train_rows = split["train_rows"]
    train_end_hour = df.loc[train_rows - 1, "hour"]

    assert split["x_train_scaled"].shape[0] + split["x_test_scaled"].shape[0] == usable_rows
    assert pd.to_datetime(split["test_hours"]).min() > pd.to_datetime(train_end_hour)
    assert np.allclose(split["x_train_scaled"].mean().to_numpy(), 0.0, atol=1e-12)
    assert not np.allclose(split["x_test_scaled"].mean().to_numpy(), 0.0, atol=1e-3)
    assert split["impute_values"].equals(df.loc[: train_rows - 1, feature_columns].median(numeric_only=True))


def test_prepare_model_matrix_raises_for_missing_feature_column() -> None:
    df = synthetic_hourly()

    with pytest.raises(KeyError):
        prepare_model_matrix(df, ["missing_feature"])
