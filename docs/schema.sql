CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    source_ip VARCHAR(45) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INT NOT NULL,
    response_time_ms FLOAT,
    bytes_sent INT NOT NULL,
    user_agent TEXT,
    is_anomaly BOOLEAN DEFAULT NULL,
    anomaly_score FLOAT DEFAULT NULL,
    lstm_is_anomaly BOOLEAN DEFAULT NULL,
    lstm_anomaly_score FLOAT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_logs_timestamp ON logs(timestamp);
CREATE INDEX idx_logs_is_anomaly ON logs(is_anomaly);

-- Shared state for cross-replica Slack alert throttling.
-- A single row (id=1) tracks the last time an alert was sent, so multiple
-- ingestion replicas share one cooldown instead of each having their own.
CREATE TABLE IF NOT EXISTS alert_state (
    id INT PRIMARY KEY DEFAULT 1,
    last_alert_sent_at TIMESTAMP,
    CONSTRAINT single_row CHECK (id = 1)
);
INSERT INTO alert_state (id, last_alert_sent_at)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;
