import os

import numpy as np
import pandas as pd
import joblib
import torch
import torch.nn as nn
from numpy.lib.stride_tricks import sliding_window_view
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine

from features import compute_windowed_ip_count, impute_response_time, FEATURE_COLUMNS

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://admin:admin123@localhost:5432/logdb"
)
WINDOW_SIZE = int(os.environ.get("LSTM_WINDOW_SIZE", "20"))
MAX_WINDOWS = int(os.environ.get("LSTM_MAX_WINDOWS", "20000"))  # cap for CPU training time
EPOCHS = int(os.environ.get("LSTM_EPOCHS", "8"))
BATCH_SIZE = int(os.environ.get("LSTM_BATCH_SIZE", "64"))
HIDDEN_SIZE = 32
LATENT_SIZE = 16
CONTAMINATION = 0.07  # matched to Isolation Forest for a fair comparison

engine = create_engine(DATABASE_URL)
df = pd.read_sql("SELECT * FROM logs", engine)
print(f"Loaded {len(df)} logs")

df["timestamp"] = pd.to_datetime(df["timestamp"])
df["request_count_per_ip"] = compute_windowed_ip_count(df)
df, response_time_median = impute_response_time(df)

# Global time order — this is what lets the LSTM see traffic-shape patterns
# (e.g. a burst of requests) that a row-by-row model like Isolation Forest cannot.
df = df.sort_values("timestamp").reset_index(drop=True)

features = df[FEATURE_COLUMNS].values.astype("float32")
scaler = StandardScaler()
features_scaled = scaler.fit_transform(features).astype("float32")

print(f"Building sliding windows of size {WINDOW_SIZE}...")
windows = sliding_window_view(features_scaled, window_shape=(WINDOW_SIZE, len(FEATURE_COLUMNS)))
windows = windows.reshape(-1, WINDOW_SIZE, len(FEATURE_COLUMNS))
print(f"Total windows available: {windows.shape[0]}")

if windows.shape[0] > MAX_WINDOWS:
    idx = np.random.choice(windows.shape[0], size=MAX_WINDOWS, replace=False)
    windows = windows[idx]
    print(f"Subsampled to {MAX_WINDOWS} windows for training speed")

X = torch.from_numpy(windows)
dataset = torch.utils.data.TensorDataset(X)
loader = torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)


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


device = torch.device("cpu")
model = LSTMAutoencoder(len(FEATURE_COLUMNS), HIDDEN_SIZE, LATENT_SIZE, WINDOW_SIZE).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
criterion = nn.MSELoss()

print(f"Training for {EPOCHS} epochs on {len(dataset)} windows...")
model.train()
for epoch in range(EPOCHS):
    total_loss = 0.0
    for (batch,) in loader:
        batch = batch.to(device)
        optimizer.zero_grad()
        reconstructed = model(batch)
        loss = criterion(reconstructed, batch)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * batch.size(0)
    avg_loss = total_loss / len(dataset)
    print(f"Epoch {epoch + 1}/{EPOCHS} - avg reconstruction MSE: {avg_loss:.5f}")

# --- Determine anomaly threshold from reconstruction error distribution ---
model.eval()
with torch.no_grad():
    reconstructed = model(X)
    errors = ((reconstructed - X) ** 2).mean(dim=(1, 2)).numpy()

threshold = float(np.percentile(errors, (1 - CONTAMINATION) * 100))
print(f"\nReconstruction error stats: mean={errors.mean():.5f}, median={np.median(errors):.5f}")
print(f"Anomaly threshold (top {CONTAMINATION*100:.0f}% = {(1-CONTAMINATION)*100:.0f}th percentile): {threshold:.5f}")
print(f"Windows above threshold: {(errors > threshold).sum()} / {len(errors)}")

torch.save(model.state_dict(), "lstm_model.pt")
joblib.dump(scaler, "lstm_scaler.pkl")
joblib.dump(response_time_median, "lstm_response_time_median.pkl")
joblib.dump(threshold, "lstm_threshold.pkl")
joblib.dump(WINDOW_SIZE, "lstm_window_size.pkl")
print("\nSaved lstm_model.pt, lstm_scaler.pkl, lstm_response_time_median.pkl, lstm_threshold.pkl, lstm_window_size.pkl")
