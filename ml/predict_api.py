import pandas as pd
import joblib
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Anomaly Scoring API")

model = joblib.load("model.pkl")
scaler = joblib.load("scaler.pkl")

# Note: this endpoint needs request_count_per_ip, which requires knowing
# how many times this IP has appeared before. For now we pass it in as
# part of the request — the ingestion service will look it up.
class PredictIn(BaseModel):
    response_time_ms: float
    status_code: int
    request_count_per_ip: int

class PredictOut(BaseModel):
    is_anomaly: bool
    anomaly_score: float

@app.post("/predict", response_model=PredictOut)
def predict(log: PredictIn):
    features = pd.DataFrame([{
        "response_time_ms": log.response_time_ms,
        "status_code": log.status_code,
        "request_count_per_ip": log.request_count_per_ip,
    }])
    features_scaled = scaler.transform(features)

    prediction = model.predict(features_scaled)[0]   # -1 = anomaly, 1 = normal
    score = model.decision_function(features_scaled)[0]  # lower = more anomalous

    return PredictOut(
        is_anomaly=bool(prediction == -1),
        anomaly_score=float(score),
    )

@app.get("/health")
def health_check():
    return {"status": "ok"}