import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features import compute_windowed_ip_count, impute_response_time, FEATURE_COLUMNS


def make_df(rows):
    """Helper: rows is a list of (source_ip, timestamp_str) tuples.
    Returns a DataFrame with a default RangeIndex, in the SAME order as rows.
    """
    df = pd.DataFrame({
        "source_ip": [r[0] for r in rows],
        "timestamp": pd.to_datetime([r[1] for r in rows]),
    })
    return df


class TestComputeWindowedIpCount:
    def test_single_request_counts_as_one(self):
        df = make_df([("1.1.1.1", "2026-01-01 00:00:00")])
        counts = compute_windowed_ip_count(df, window_seconds=60)
        assert counts.loc[0] == 1

    def test_requests_within_window_are_counted_together(self):
        # Three requests from the same IP, all within 60 seconds of each other
        df = make_df([
            ("1.1.1.1", "2026-01-01 00:00:00"),
            ("1.1.1.1", "2026-01-01 00:00:20"),
            ("1.1.1.1", "2026-01-01 00:00:40"),
        ])
        counts = compute_windowed_ip_count(df, window_seconds=60)
        # Row 2 (index 2, the last one chronologically) should see all 3
        assert counts.loc[2] == 3

    def test_requests_outside_window_are_excluded(self):
        # This is the exact bug class we hit: a request from 5 minutes ago
        # must NOT inflate the count for a request happening now.
        df = make_df([
            ("1.1.1.1", "2026-01-01 00:00:00"),  # 5 minutes before the second request
            ("1.1.1.1", "2026-01-01 00:05:00"),
        ])
        counts = compute_windowed_ip_count(df, window_seconds=60)
        # Row 1 (index 1, the later request) should only see itself
        assert counts.loc[1] == 1

    def test_different_ips_counted_independently(self):
        df = make_df([
            ("1.1.1.1", "2026-01-01 00:00:00"),
            ("2.2.2.2", "2026-01-01 00:00:01"),
            ("1.1.1.1", "2026-01-01 00:00:02"),
        ])
        counts = compute_windowed_ip_count(df, window_seconds=60)
        assert counts.loc[2] == 2  # second request from 1.1.1.1, sees both
        assert counts.loc[1] == 1  # only request from 2.2.2.2


class TestImputeResponseTime:
    def test_no_missing_values_unchanged(self):
        df = pd.DataFrame({"response_time_ms": [100.0, 200.0, 150.0]})
        result_df, median = impute_response_time(df)
        assert result_df["has_response_time"].tolist() == [1, 1, 1]
        assert result_df["response_time_ms"].tolist() == [100.0, 200.0, 150.0]
        assert median == 150.0  # median of [100, 150, 200]

    def test_missing_values_flagged_and_imputed(self):
        # This is the exact scenario that broke real-world NASA log ingestion:
        # a mix of real and missing response times must not crash or silently
        # drop the missing rows.
        df = pd.DataFrame({"response_time_ms": [100.0, None, 200.0]})
        result_df, median = impute_response_time(df)
        assert result_df["has_response_time"].tolist() == [1, 0, 1]
        assert result_df["response_time_ms"].iloc[1] == median  # imputed with the median
        assert median == 150.0  # median of [100, 200] (NaN excluded) = (100+200)/2

    def test_serving_time_uses_provided_median_not_recomputed(self):
        # At serving time we must use the TRAINING median, not recompute one
        # from a single incoming row (which would be meaningless/undefined).
        df = pd.DataFrame({"response_time_ms": [None]})
        result_df, median_used = impute_response_time(df, median=123.45)
        assert median_used == 123.45
        assert result_df["response_time_ms"].iloc[0] == 123.45
        assert result_df["has_response_time"].iloc[0] == 0

    def test_all_missing_uses_provided_median(self):
        df = pd.DataFrame({"response_time_ms": [None, None]})
        result_df, median_used = impute_response_time(df, median=99.0)
        assert (result_df["response_time_ms"] == 99.0).all()
        assert (result_df["has_response_time"] == 0).all()


class TestFeatureColumns:
    def test_feature_columns_match_expected_set(self):
        # Guards against someone silently reordering or renaming a column
        # in only one of train.py / predict_api.py without updating this list.
        assert FEATURE_COLUMNS == [
            "response_time_ms",
            "has_response_time",
            "status_code",
            "request_count_per_ip",
        ]
