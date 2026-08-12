"""
Ingestion API — the front door of the pipeline.
Calls both the Isolation Forest and LSTM ML scoring services after every insert.

Run locally with:
    uvicorn main:app --reload
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional, List

import requests
from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text

from database import Base, engine, get_db
from models import Log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingestion")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Log Ingestion API")

# CORS: allows a browser-based frontend (e.g. the React dashboard planned
# for a later step) served from a different origin to call this API.
# Origins are configurable via env var so this stays safe by default —
# an empty/unset ALLOWED_ORIGINS means no cross-origin requests are permitted.
_allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

ML_PREDICT_URL = "http://ml:8001/predict"
LSTM_PREDICT_URL = "http://ml:8001/predict_lstm"
LSTM_WINDOW_SIZE = 20
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_ALERT_COOLDOWN_SECONDS = int(os.environ.get("SLACK_ALERT_COOLDOWN_SECONDS", "30"))


# ---- request/response schemas ----

class LogIn(BaseModel):
    timestamp: datetime
    source_ip: str
    endpoint: str
    method: str
    status_code: int
    response_time_ms: Optional[float] = None
    bytes_sent: int
    user_agent: Optional[str] = None


class LogOut(LogIn):
    id: int
    is_anomaly: Optional[bool] = None
    anomaly_score: Optional[float] = None
    lstm_is_anomaly: Optional[bool] = None
    lstm_anomaly_score: Optional[float] = None

    class Config:
        from_attributes = True


# ---- helpers ----

def post_with_retry(url: str, json_payload: dict, timeout: float, max_attempts: int = 2):
    """POSTs with a small bounded retry for transient failures (e.g. a brief
    network blip between containers). Not retried: this raises on final
    failure, same as a plain requests.post + raise_for_status would — the
    caller's existing try/except still handles the ultimate failure case.
    Deliberately short and bounded (no exponential backoff into minutes)
    since ML scoring should stay fast; a slow ml service should just fail
    and leave the log unscored rather than blocking ingestion for a long time.
    """
    last_exception = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.post(url, json=json_payload, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            last_exception = e
            if attempt < max_attempts:
                time.sleep(0.2 * attempt)  # 0.2s, then 0.4s, etc.
    raise last_exception


def score_log_isolation_forest(db: Session, db_log: Log):
    """Calls the Isolation Forest ML service and writes is_anomaly/anomaly_score."""
    window_start = db_log.timestamp - timedelta(seconds=60)
    request_count = db.query(func.count(Log.id)).filter(
        Log.source_ip == db_log.source_ip,
        Log.timestamp >= window_start,
        Log.timestamp <= db_log.timestamp,
    ).scalar()

    try:
        response = post_with_retry(ML_PREDICT_URL, {
            "response_time_ms": db_log.response_time_ms,
            "status_code": db_log.status_code,
            "request_count_per_ip": request_count,
        }, timeout=2)
        result = response.json()
        db_log.is_anomaly = result["is_anomaly"]
        db_log.anomaly_score = result["anomaly_score"]
    except Exception as e:
        logger.warning(f"Isolation Forest scoring failed: {e}")

    return request_count


def score_log_lstm(db: Session, db_log: Log, latest_request_count: int):
    """Calls the LSTM ML service with a time-ordered window of the last
    LSTM_WINDOW_SIZE logs (globally, not per-IP). Skips scoring if there's
    not yet enough history in the table.
    """
    recent_logs = (
        db.query(Log)
        .filter(Log.timestamp <= db_log.timestamp)
        .order_by(desc(Log.timestamp))
        .limit(LSTM_WINDOW_SIZE)
        .all()
    )

    if len(recent_logs) < LSTM_WINDOW_SIZE:
        # Not enough history yet (e.g. early in the table's life) — skip.
        return

    # recent_logs is newest-first; reverse to oldest-first for the model,
    # which was trained on chronologically ordered windows.
    recent_logs = list(reversed(recent_logs))

    window = []
    for row in recent_logs:
        if row.id == db_log.id:
            # Use the freshly computed count for the current row, since
            # db_log may not be committed/queryable consistently yet.
            count = latest_request_count
        else:
            row_window_start = row.timestamp - timedelta(seconds=60)
            count = db.query(func.count(Log.id)).filter(
                Log.source_ip == row.source_ip,
                Log.timestamp >= row_window_start,
                Log.timestamp <= row.timestamp,
            ).scalar()

        window.append({
            "response_time_ms": row.response_time_ms,
            "status_code": row.status_code,
            "request_count_per_ip": count,
        })

    try:
        response = post_with_retry(LSTM_PREDICT_URL, {"window": window}, timeout=3)
        result = response.json()
        db_log.lstm_is_anomaly = result["is_anomaly"]
        db_log.lstm_anomaly_score = result["anomaly_score"]
    except Exception as e:
        logger.warning(f"LSTM scoring failed: {e}")


def _claim_alert_slot(db: Session) -> bool:
    """Atomically checks the shared cooldown and claims the alert slot if
    eligible, using a single UPDATE ... WHERE so concurrent ingestion
    replicas can't both pass the check before either one writes. Returns
    True if this call should send the alert, False if still in cooldown.
    """
    result = db.execute(
        text("""
            UPDATE alert_state
            SET last_alert_sent_at = :now
            WHERE id = 1
              AND (
                  last_alert_sent_at IS NULL
                  OR :now - last_alert_sent_at >= (:cooldown || ' seconds')::interval
              )
        """),
        {"now": datetime.utcnow(), "cooldown": SLACK_ALERT_COOLDOWN_SECONDS},
    )
    db.commit()
    return result.rowcount > 0


def send_slack_alert(db: Session, db_log: Log):
    """Posts a Slack message if alerting is configured. Never raises —
    a broken/missing webhook must never take down log ingestion.
    Throttled to at most one alert per SLACK_ALERT_COOLDOWN_SECONDS across
    ALL ingestion replicas (state lives in Postgres, not in-process), to
    avoid flooding the channel during a burst of anomalies.
    """
    if not SLACK_WEBHOOK_URL:
        return

    flagged_by = []
    if db_log.is_anomaly:
        flagged_by.append(f"Isolation Forest (score={db_log.anomaly_score:.3f})")
    if db_log.lstm_is_anomaly:
        flagged_by.append(f"LSTM (score={db_log.lstm_anomaly_score:.3f})")

    if not flagged_by:
        return

    if not _claim_alert_slot(db):
        return

    message_text = (
        f":rotating_light: *Anomaly detected* — {db_log.method} {db_log.endpoint} "
        f"[{db_log.status_code}] from `{db_log.source_ip}`\n"
        f"Flagged by: {', '.join(flagged_by)}"
    )

    try:
        requests.post(SLACK_WEBHOOK_URL, json={"text": message_text}, timeout=2)
    except Exception as e:
        logger.warning(f"Slack alert failed: {e}")


def score_log(db: Session, db_log: Log):
    request_count = score_log_isolation_forest(db, db_log)
    score_log_lstm(db, db_log, request_count)
    db.commit()
    db.refresh(db_log)
    send_slack_alert(db, db_log)


# ---- endpoints ----

@app.post("/logs", response_model=LogOut)
def create_log(log: LogIn, db: Session = Depends(get_db)):
    db_log = Log(**log.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    score_log(db, db_log)

    return db_log


@app.get("/logs", response_model=List[LogOut])
def read_logs(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)):
    return db.query(Log).order_by(desc(Log.timestamp)).limit(limit).all()


@app.get("/health")
def health_check():
    return {"status": "ok"}
