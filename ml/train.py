import pandas as pd
import joblib
from sqlalchemy import create_engine
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

DATABASE_URL = "postgresql://admin:admin123@localhost:5432/logdb"
engine = create_engine(DATABASE_URL)

df = pd.read_sql("SELECT * FROM logs", engine)
print(f"Training on {len(df)} logs")

# --- Features ---
# 1. response_time_ms (raw)
# 2. status_code (raw — errors like 500 cluster differently from 200s)
# 3. request_count_per_ip (how many times this IP appears — catches hammering)
ip_counts = df["source_ip"].value_counts()
df["request_count_per_ip"] = df["source_ip"].map(ip_counts)

features = df[["response_time_ms", "status_code", "request_count_per_ip"]]

# Scale features so no single one dominates
scaler = StandardScaler()
features_scaled = scaler.fit_transform(features)

# contamination = expected proportion of anomalies in the data
# start at 0.1 (10%), tune later based on results
model = IsolationForest(n_estimators=200, contamination=0.1, random_state=42)
model.fit(features_scaled)

# Save both the model and the scaler (need scaler at prediction time too)
joblib.dump(model, "model.pkl")
joblib.dump(scaler, "scaler.pkl")

# Quick sanity check
df["anomaly_pred"] = model.predict(features_scaled)  # -1 = anomaly, 1 = normal
print("\nPrediction counts:")
print(df["anomaly_pred"].value_counts())
print("\nSample flagged anomalies:")
print(df[df["anomaly_pred"] == -1][["source_ip", "status_code", "response_time_ms", "request_count_per_ip"]].head(10))