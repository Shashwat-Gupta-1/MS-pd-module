import uuid
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, DateTime, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class PDSession(Base):
    __tablename__ = "pd_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    officer_id = Column(String(36), ForeignKey("officers.id"), nullable=False, index=True)
    channel = Column(String(20), nullable=False, default="ground")  # ground only for v1
    recording_url = Column(String(500), nullable=True)
    consent_captured = Column(Boolean, nullable=False, default=False)
    consent_timestamp = Column(DateTime(timezone=True), nullable=True)
    transcript_raw = Column(Text, nullable=True)
    raw_asr_json = Column(JSON, nullable=True)
    duration_sec = Column(Float, nullable=True)
    language = Column(String(20), nullable=True)
    status = Column(String(30), nullable=False, default="recorded")  # recorded | transcribing | transcribed | failed_stt | complete
    gap_round_count = Column(Integer, nullable=False, default=0)
    checklist_fully_covered = Column(Boolean, nullable=False, default=False)
    is_session_active = Column(Boolean, nullable=False, default=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    application = relationship("Application", backref="pd_sessions")
    officer = relationship("Officer", backref="pd_sessions")
