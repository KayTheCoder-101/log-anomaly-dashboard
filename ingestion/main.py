"""
Ingestion API — the front door of the pipeline.
Now also calls the ML scoring service after every insert.

Run locally with:
    uvicorn main:app --reload
"""

from datetime import datetime
from typing import Optional, List

import requests
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database import Base, engine, get_db
from models import Log

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Log Ingestion API")

ML_PREDICT_URL = "http://127.0.0.1:8001/predict"


# ---- request/response schemas ----

class LogIn(BaseModel):
    timestamp: datetime
    source_ip: str
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    bytes_sent: int
    user_agent: Optional[str] = None


class LogOut(LogIn):
    id: int
    is_anomaly: Optional[bool] = None
    anomaly_score: Optional[float] = None

    class Config:
        from_attributes = True


# ---- helper ----

def score_log(db: Session, db_log: Log):
    """Calls the ML service and writes is_anomaly/anomaly_score back onto db_log."""
    request_count = db.query(func.count(Log.id)).filter(Log.source_ip == db_log.source_ip).scalar()

    try:
        response = requests.post(ML_PREDICT_URL, json={
            "response_time_ms": db_log.response_time_ms,
            "status_code": db_log.status_code,
            "request_count_per_ip": request_count,
        }, timeout=2)
        response.raise_for_status()
        result = response.json()
        db_log.is_anomaly = result["is_anomaly"]
        db_log.anomaly_score = result["anomaly_score"]
        db.commit()
        db.refresh(db_log)
    except Exception as e:
        # If ML service is down, don't crash ingestion — just leave it unscored.
        print(f"ML scoring failed: {e}")


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
def read_logs(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Log).order_by(desc(Log.timestamp)).limit(limit).all()


@app.get("/health")
def health_check():
    return {"status": "ok"}