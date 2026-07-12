from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from database import Base

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False)
    source_ip = Column(String(45), nullable=False)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    bytes_sent = Column(Integer, nullable=False)
    user_agent = Column(String, nullable=True)
    is_anomaly = Column(Boolean, nullable=True, default=None)
    anomaly_score = Column(Float, nullable=True, default=None)
    created_at = Column(DateTime, server_default=func.now())