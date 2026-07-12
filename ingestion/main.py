from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import Base, engine, get_db
from models import Log

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Log Ingestion API")

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

@app.post("/logs", response_model=LogOut)
def create_log(log: LogIn, db: Session = Depends(get_db)):
    db_log = Log(**log.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

@app.get("/logs", response_model=List[LogOut])
def read_logs(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Log).order_by(desc(Log.timestamp)).limit(limit).all()

@app.get("/health")
def health_check():
    return {"status": "ok"}