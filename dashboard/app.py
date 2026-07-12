import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from streamlit_autorefresh import st_autorefresh

DATABASE_URL = "postgresql://admin:admin123@localhost:5432/logdb"
engine = create_engine(DATABASE_URL)

st.set_page_config(page_title="Log Anomaly Dashboard", layout="wide")

# Auto-refresh every 5 seconds
st_autorefresh(interval=5000, key="refresh")

st.title("Log Analysis Dashboard with Anomaly Detection")


@st.cache_data(ttl=4)
def load_data():
    return pd.read_sql("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 500", engine)


df = load_data()

if df.empty:
    st.warning("No logs yet. Start the generator to see data here.")
    st.stop()

# ---- Summary stats ----
total_logs = len(df)
anomaly_count = int(df["is_anomaly"].fillna(False).sum())
anomaly_rate = round((anomaly_count / total_logs) * 100, 1) if total_logs else 0

col1, col2, col3 = st.columns(3)
col1.metric("Total Logs (last 500)", total_logs)
col2.metric("Anomalies Detected", anomaly_count)
col3.metric("Anomaly Rate", f"{anomaly_rate}%")

st.divider()

# ---- Charts ----
chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    st.subheader("Log Volume Over Time")
    volume = df.set_index("timestamp").resample("10s", on=None).size() if False else None
    df_sorted = df.sort_values("timestamp")
    df_sorted["minute"] = pd.to_datetime(df_sorted["timestamp"]).dt.floor("10s")
    volume_by_time = df_sorted.groupby("minute").size()
    st.line_chart(volume_by_time)

with chart_col2:
    st.subheader("Status Code Breakdown")
    status_counts = df["status_code"].value_counts().sort_index()
    st.bar_chart(status_counts)

st.divider()

# ---- Anomaly feed ----
st.subheader("Live Anomaly Feed")

anomalies = df[df["is_anomaly"] == True].sort_values("timestamp", ascending=False)

if anomalies.empty:
    st.info("No anomalies detected yet.")
else:
    display_cols = ["timestamp", "source_ip", "endpoint", "status_code", "response_time_ms", "anomaly_score"]
    st.dataframe(
        anomalies[display_cols].style.applymap(lambda _: "background-color: #ffcccc"),
        use_container_width=True,
    )

st.divider()

# ---- Recent logs table ----
st.subheader("Recent Logs")
st.dataframe(
    df[["timestamp", "source_ip", "endpoint", "method", "status_code", "response_time_ms", "is_anomaly"]].head(50),
    use_container_width=True,
)