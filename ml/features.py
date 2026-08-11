"""Shared feature engineering for both the Isolation Forest and LSTM models.

Centralizing this avoids train/serve skew: every place that computes
features (training scripts, the prediction API) imports from here instead
of reimplementing the same logic slightly differently.
"""
import pandas as pd


def compute_windowed_ip_count(df: pd.DataFrame, window_seconds: int = 60) -> pd.Series:
    """For each row, count how many requests from the same source_ip
    occurred in the trailing `window_seconds` window (inclusive of the row itself).
    Requires df to have 'source_ip' and 'timestamp' (datetime) columns.
    Returns a Series aligned to df's index.
    """
    df = df.sort_values(["source_ip", "timestamp"])

    def rolling_count(group):
        times = group["timestamp"]
        counts = []
        for t in times:
            window_start = t - pd.Timedelta(seconds=window_seconds)
            counts.append(((times >= window_start) & (times <= t)).sum())
        return pd.Series(counts, index=group.index)

    counts = df.groupby("source_ip", group_keys=False).apply(rolling_count)
    return counts.reindex(df.index)


def impute_response_time(df: pd.DataFrame, median: float = None):
    """Adds 'has_response_time' flag and fills missing response_time_ms.
    If median is None, computes it from the data (training time).
    If median is provided, uses it (serving time, using the training median).
    Returns (df, median_used).
    """
    df = df.copy()
    df["has_response_time"] = df["response_time_ms"].notna().astype(int)
    if median is None:
        median = df["response_time_ms"].median(skipna=True)
    df["response_time_ms"] = df["response_time_ms"].fillna(median)
    return df, median


FEATURE_COLUMNS = ["response_time_ms", "has_response_time", "status_code", "request_count_per_ip"]
