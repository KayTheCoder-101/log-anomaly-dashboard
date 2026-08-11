from typing import List, Optional

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from fastapi import FastAPI
from pydantic import BaseModel

from features import FEATURE_COLUMNS

app = FastAPI(title="Anomaly Scoring API")

# ---- Isolation Forest artifacts ----
if_model = joblib.load("model.pkl")
if_scaler = joblib.load("scaler.pkl")
if_response_time_median = joblib.load("response_time_median.pkl")

# ---- LSTM artifacts ----
lstm_scaler = joblib.load("lstm_scaler.pkl")
lstm_response_time_median = joblib.load("lstm_response_time_median.pkl")
lstm_threshold = joblib.load("lstm_threshold.pkl")
lstm_window_size = joblib.load("lstm_window_size.pkl")


class LSTMAutoencoder(nn.Module):
    def __init__(self, n_features, hidden_size, latent_size, seq_len):
        super().__init__()
        self.seq_len = seq_len
        self.encoder = nn.LSTM(n_features, hidden_size, batch_first=True)
        self.to_latent = nn.Linear(hidden_size, latent_size)
        self.from_latent = nn.Linear(latent_size, hidden_size)
        self.decoder = nn.LSTM(hidden_size, hidden_size, batch_first=True)
        self.output_layer = nn.Linear(hidden_size, n_features)

    def forward(self, x):
        _, (h_n, _) = self.encoder(x)
        latent = self.to_latent(h_n[-1])
        hidden = self.from_latent(latent)
        hidden_seq = hidden.unsqueeze(1).repeat(1, self.seq_len, 1)
        decoded, _ = self.decoder(hidden_seq)
        return self.output_layer(decoded)


lstm_model = LSTMAutoencoder(len(FEATURE_COLUMNS), hidden_size=32, latent_size=16, seq_len=lstm_window_size)
lstm_model.load_state_dict(torch.load("lstm_model.pt", map_location="cpu"))
lstm_model.eval()


# ---- Isolation Forest endpoint ----

class PredictIn(BaseModel):
    response_time_ms: Optional[float] = None
    status_code: int
    request_count_per_ip: int


class PredictOut(BaseModel):
    is_anomaly: bool
    anomaly_score: float


@app.post("/predict", response_model=PredictOut)
def predict(log: PredictIn):
    has_response_time = log.response_time_ms is not None
    response_time_value = log.response_time_ms if has_response_time else if_response_time_median

    features = pd.DataFrame([{
        "response_time_ms": response_time_value,
        "has_response_time": int(has_response_time),
        "status_code": log.status_code,
        "request_count_per_ip": log.request_count_per_ip,
    }])[FEATURE_COLUMNS]
    features_scaled = if_scaler.transform(features)

    prediction = if_model.predict(features_scaled)[0]
    score = if_model.decision_function(features_scaled)[0]

    return PredictOut(
        is_anomaly=bool(prediction == -1),
        anomaly_score=float(score),
    )


# ---- LSTM endpoint ----

class LogEntry(BaseModel):
    response_time_ms: Optional[float] = None
    status_code: int
    request_count_per_ip: int


class LSTMPredictIn(BaseModel):
    window: List[LogEntry]  # chronological order, oldest first


@app.post("/predict_lstm", response_model=PredictOut)
def predict_lstm(payload: LSTMPredictIn):
    if len(payload.window) != lstm_window_size:
        return PredictOut(is_anomaly=False, anomaly_score=0.0)

    rows = []
    for entry in payload.window:
        has_response_time = entry.response_time_ms is not None
        response_time_value = entry.response_time_ms if has_response_time else lstm_response_time_median
        rows.append([
            response_time_value,
            int(has_response_time),
            entry.status_code,
            entry.request_count_per_ip,
        ])

    arr = np.array(rows, dtype="float32")
    arr_scaled = lstm_scaler.transform(arr).astype("float32")
    x = torch.from_numpy(arr_scaled).unsqueeze(0)

    with torch.no_grad():
        reconstructed = lstm_model(x)
        error = ((reconstructed - x) ** 2).mean().item()

    return PredictOut(
        is_anomaly=bool(error > lstm_threshold),
        anomaly_score=float(error),
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}
