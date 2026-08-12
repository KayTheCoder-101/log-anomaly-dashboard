import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
import main


client = TestClient(main.app)


def make_mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.raise_for_status.return_value = None
    return mock


class TestHealthCheck:
    def test_health_check_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCreateLog:
    @patch("main.requests.post")
    def test_create_log_returns_expected_shape(self, mock_post):
        # Mock both the Isolation Forest and LSTM prediction calls to avoid
        # needing a real ml service or trained models for this test.
        mock_post.return_value = make_mock_response({
            "is_anomaly": False,
            "anomaly_score": 0.1,
        })

        payload = {
            "timestamp": "2026-01-01T00:00:00",
            "source_ip": "10.0.0.1",
            "endpoint": "/test",
            "method": "GET",
            "status_code": 200,
            "response_time_ms": 100.0,
            "bytes_sent": 500,
            "user_agent": None,
        }
        response = client.post("/logs", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["source_ip"] == "10.0.0.1"
        assert data["endpoint"] == "/test"
        # Scoring fields must be present in the response shape, whatever
        # their value (this guards against accidentally dropping a field
        # from the LogOut schema).
        assert "is_anomaly" in data
        assert "anomaly_score" in data
        assert "lstm_is_anomaly" in data
        assert "lstm_anomaly_score" in data

    @patch("main.requests.post")
    def test_create_log_with_missing_response_time_is_accepted(self, mock_post):
        # This is the exact scenario that broke real-world NASA log
        # ingestion before response_time_ms was made Optional.
        mock_post.return_value = make_mock_response({
            "is_anomaly": False,
            "anomaly_score": 0.1,
        })

        payload = {
            "timestamp": "2026-01-01T00:00:00",
            "source_ip": "10.0.0.2",
            "endpoint": "/no-response-time",
            "method": "GET",
            "status_code": 200,
            "response_time_ms": None,
            "bytes_sent": 500,
            "user_agent": None,
        }
        response = client.post("/logs", json=payload)

        assert response.status_code == 200
        assert response.json()["response_time_ms"] is None

    @patch("main.requests.post")
    def test_ml_scoring_failure_does_not_break_ingestion(self, mock_post):
        # If the ml service is down/unreachable, the log must still be
        # accepted and stored — just left unscored, not rejected.
        mock_post.side_effect = Exception("connection refused")

        payload = {
            "timestamp": "2026-01-01T00:00:00",
            "source_ip": "10.0.0.3",
            "endpoint": "/ml-down-test",
            "method": "GET",
            "status_code": 200,
            "response_time_ms": 100.0,
            "bytes_sent": 500,
            "user_agent": None,
        }
        response = client.post("/logs", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["is_anomaly"] is None
        assert data["anomaly_score"] is None


class TestReadLogs:
    def test_read_logs_returns_a_list(self):
        response = client.get("/logs?limit=5")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
