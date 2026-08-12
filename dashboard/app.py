import hmac
import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine
from streamlit_autorefresh import st_autorefresh

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:5432/logdb")

st.set_page_config(page_title="Log Anomaly Dashboard", page_icon="📊", layout="wide")

# ---- Auth gate ----
# Simple shared-password gate. Not a real user system — intentionally minimal
# for a single-operator dashboard. If DASHBOARD_PASSWORD is unset, auth is
# disabled entirely (useful for local dev without setting up a password).
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

if DASHBOARD_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Log Anomaly Dashboard")
        entered_password = st.text_input("Password", type="password")
        if st.button("Log in"):
            if hmac.compare_digest(entered_password, DASHBOARD_PASSWORD):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")
        st.stop()

# ---- Custom theme (dark, classy) ----
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --void:#0A0C10; --panel:#12151C; --panel-2:#171B24; --border:#232833;
    --text-primary:#E4E7EC; --text-secondary:#8B95A5; --text-muted:#5B6472;
    --signal:#1D9E75; --signal-soft:#5DCAA5;
    --anomaly:#D85A30; --anomaly-soft:#F0997B;
}

.stApp {
    background-color: var(--void);
    background-image:
        linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
    background-size: 32px 32px;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; font-weight: 500 !important; }

[data-testid="stSidebar"] {
    background-color: var(--panel);
    border-right: 1px solid var(--border);
}

[data-testid="stMetric"] {
    background-color: var(--panel-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
}
[data-testid="stMetricValue"] {
    font-family: 'Space Grotesk', sans-serif;
    color: var(--text-primary);
}
[data-testid="stMetricLabel"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: var(--panel);
    border: 1px solid var(--border);
    border-radius: 14px;
}

[data-testid="stDataFrame"] {
    font-family: 'JetBrains Mono', monospace;
    border: 1px solid var(--border);
    border-radius: 10px;
}

span[data-baseweb="tag"] {
    background-color: rgba(29,158,117,0.16) !important;
    border: 1px solid var(--signal) !important;
    color: var(--signal-soft) !important;
    border-radius: 16px !important;
}

.stCheckbox label { color: var(--text-secondary); font-size: 12.5px; }

.stCaption, [data-testid="stCaptionContainer"] {
    font-family: 'JetBrains Mono', monospace;
    color: var(--text-muted) !important;
}
</style>
""", unsafe_allow_html=True)

st_autorefresh(interval=10000, key="refresh")


@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=0)


engine = get_engine()


@st.cache_data(ttl=4)
def load_data():
    df = pd.read_sql("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 500", engine)
    df["is_anomaly"] = df["is_anomaly"].fillna(False).astype(bool)
    df["anomaly_score"] = pd.to_numeric(df["anomaly_score"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


df = load_data()

if df.empty:
    st.warning("No logs yet. Start the generator to see data here.")
    st.stop()

# ---- Sidebar filters ----
st.sidebar.header("Filters")

status_options = sorted(df["status_code"].unique().tolist())
selected_statuses = st.sidebar.multiselect("Status codes", status_options, default=status_options)

endpoint_options = sorted(df["endpoint"].unique().tolist())
selected_endpoints = st.sidebar.multiselect("Endpoints", endpoint_options, default=endpoint_options)

show_anomalies_only = st.sidebar.checkbox("Show anomalies only (Recent Logs)", value=False)

st.sidebar.caption(f"Data refreshes every 10s · {len(df)} rows loaded")

filtered_df = df[df["status_code"].isin(selected_statuses) & df["endpoint"].isin(selected_endpoints)]

# ---- Title ----
st.title("📊 Log Analysis Dashboard with Anomaly Detection")
st.caption("Real-time log ingestion, ML-based anomaly scoring, and live monitoring")

# ---- Summary stats ----
total_logs = len(filtered_df)
anomaly_count = int(filtered_df["is_anomaly"].sum())
anomaly_rate = round((anomaly_count / total_logs) * 100, 1) if total_logs else 0

with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Logs (filtered)", total_logs)
    col2.metric("Anomalies Detected", anomaly_count)
    col3.metric("Anomaly Rate", f"{anomaly_rate}%")

st.write("")

# ---- Charts ----
with st.container(border=True):
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("📈 Log Volume Over Time")
        df_sorted = filtered_df.sort_values("timestamp")
        df_sorted["bucket"] = df_sorted["timestamp"].dt.floor("10s")
        volume_by_time = df_sorted.groupby("bucket").size()
        st.line_chart(volume_by_time, color="#1D9E75")

    with chart_col2:
        st.subheader("📊 Status Code Breakdown")
        status_counts = filtered_df["status_code"].value_counts().sort_index()
        st.bar_chart(status_counts, color="#5DCAA5")

st.write("")

# ---- Anomaly feed ----
with st.container(border=True):
    st.subheader("🚨 Live Anomaly Feed")

    anomalies = filtered_df[filtered_df["is_anomaly"]].sort_values("timestamp", ascending=False)

    if anomalies.empty:
        st.info("No anomalies detected in the current filter selection.")
    else:
        display_cols = ["timestamp", "source_ip", "endpoint", "status_code", "response_time_ms", "anomaly_score"]
        st.dataframe(anomalies[display_cols], width="stretch", height=300)

st.write("")

# ---- Recent logs table ----
with st.container(border=True):
    st.subheader("🗒️ Recent Logs")

    logs_to_show = filtered_df[filtered_df["is_anomaly"]] if show_anomalies_only else filtered_df

    st.dataframe(
        logs_to_show[["timestamp", "source_ip", "endpoint", "method", "status_code", "response_time_ms", "is_anomaly"]].head(50),
        width="stretch",
    )