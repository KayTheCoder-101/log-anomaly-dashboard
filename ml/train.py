import os

import pandas as pd
import joblib
from sqlalchemy import create_engine
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from features import compute_windowed_ip_count, impute_response_time, FEATURE_COLUMNS

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://admin:admin123@localhost:5432/logdb"
)
engine = create_engine(DATABASE_URL)

df = pd.read_sql("SELECT * FROM logs", engine)
print(f"Training on {len(df)} logs")

df["timestamp"] = pd.to_datetime(df["timestamp"])

print("Computing time-windowed IP request counts (this may take a moment)...")
df["request_count_per_ip"] = compute_windowed_ip_count(df)

df, response_time_median = impute_response_time(df)
print(f"Response time median used for imputation: {response_time_median:.2f}ms")
print(f"Rows with missing response_time_ms: {(df['has_response_time'] == 0).sum()} / {len(df)}")

features = df[FEATURE_COLUMNS]

scaler = StandardScaler()
features_scaled = scaler.fit_transform(features)

model = IsolationForest(n_estimators=200, contamination=0.07, random_state=42)
model.fit(features_scaled)

joblib.dump(model, "model.pkl")
joblib.dump(scaler, "scaler.pkl")
joblib.dump(response_time_median, "response_time_median.pkl")

df["anomaly_pred"] = model.predict(features_scaled)
print("\nPrediction counts:")
print(df["anomaly_pred"].value_counts())
