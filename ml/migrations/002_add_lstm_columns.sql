-- Adds columns for the LSTM autoencoder's predictions, alongside the
-- existing Isolation Forest columns (is_anomaly, anomaly_score).
ALTER TABLE logs ADD COLUMN IF NOT EXISTS lstm_is_anomaly BOOLEAN DEFAULT NULL;
ALTER TABLE logs ADD COLUMN IF NOT EXISTS lstm_anomaly_score FLOAT DEFAULT NULL;
