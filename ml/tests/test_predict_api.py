import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
import predict_api


client = TestClient(predict_api.app)


class TestHealthCheck:
    def test_health_check_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestPredictIsolationForest:
    def test_normal_log_returns_valid_shape(self):
        response = client.post("/predict", json={
            "response_time_ms": 120.0,
            "status_code": 200,
            "request_count_per_ip": 1,
        })
        assert response.status_code == 200
        data = response.json()
        assert "is_anomaly" in data
        assert "anomaly_score" in data
        assert isinstance(data["is_anomaly"], bool)
        assert isinstance(data["anomaly_score"], float)

    def test_missing_response_time_does_not_error(self):
        # Real-world log sources (e.g. NASA HTTP logs) don't report this —
        # the endpoint must impute using the saved training median, not crash.
        response = client.post("/predict", json={
            "response_time_ms": None,
            "status_code": 200,
            "request_count_per_ip": 1,
        })
        assert response.status_code == 200

    def test_extreme_values_flagged_as_anomalous(self):
        # A very slow response, an error status, and a huge request count
        # from one IP should score as clearly anomalous against real
        # trained models — this is an end-to-end sanity check, not just
        # a shape check.
        response = client.post("/predict", json={
            "response_time_ms": 50000.0,
            "status_code": 500,
            "request_count_per_ip": 500,
        })
        assert response.status_code == 200
        assert response.json()["is_anomaly"] is True

    def test_missing_required_field_returns_422(self):
        response = client.post("/predict", json={
            "response_time_ms": 120.0,
            "status_code": 200,
            # request_count_per_ip omitted — required field
        })
        assert response.status_code == 422


class TestPredictLSTM:
    def _make_window(self, size, response_time_ms=120.0, status_code=200, request_count_per_ip=1):
        return [
            {
                "response_time_ms": response_time_ms,
                "status_code": status_code,
                "request_count_per_ip": request_count_per_ip,
            }
            for _ in range(size)
        ]

    def test_correct_window_size_returns_valid_shape(self):
        window = self._make_window(predict_api.lstm_window_size)
        response = client.post("/predict_lstm", json={"window": window})
        assert response.status_code == 200
        data = response.json()
        assert "is_anomaly" in data
        assert "anomaly_score" in data

    def test_wrong_window_size_returns_safe_default(self):
        # Fewer rows than the model expects (e.g. early in the table's
        # history) must not crash — should return a safe "not anomaly"
        # default rather than error, matching ingestion's graceful-skip
        # behavior for insufficient history.
        window = self._make_window(5)
        response = client.post("/predict_lstm", json={"window": window})
        assert response.status_code == 200
        data = response.json()
        assert data["is_anomaly"] is False
        assert data["anomaly_score"] == 0.0

    def test_empty_window_returns_safe_default(self):
        response = client.post("/predict_lstm", json={"window": []})
        assert response.status_code == 200
        assert response.json()["is_anomaly"] is False

    def test_missing_response_time_in_window_does_not_error(self):
        window = self._make_window(predict_api.lstm_window_size, response_time_ms=None)
        response = client.post("/predict_lstm", json={"window": window})
        assert response.status_code == 200
