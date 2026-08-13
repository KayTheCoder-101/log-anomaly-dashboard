-- Shared state for cross-replica Slack alert throttling. A single row
-- (id=1) tracks the last time an alert was sent, so multiple ingestion
-- replicas share one cooldown instead of each having their own.
CREATE TABLE IF NOT EXISTS alert_state (
    id INT PRIMARY KEY DEFAULT 1,
    last_alert_sent_at TIMESTAMP,
    CONSTRAINT single_row CHECK (id = 1)
);
INSERT INTO alert_state (id, last_alert_sent_at)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;
