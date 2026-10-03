"""PDSession model: application_id FK, channel (always ground for v1), recording_url, consent_captured, consent_timestamp, transcript_raw, status, gap_round_count, checklist_fully_covered."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PDSession(Base):
    __tablename__ = "pd_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    application_id: Mapped[Optional[str]] = mapped_column(ForeignKey("applications.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String, default="ground")        # always "ground" for v1

    recording_url: Mapped[Optional[str]] = mapped_column(String)
    consent_captured: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    transcript_raw: Mapped[Optional[str]] = mapped_column(Text)           # full transcript, "[speaker] text" lines
    status: Mapped[str] = mapped_column(String, default="uploaded")       # uploaded -> transcribing -> transcribed | failed_stt
    gap_round_count: Mapped[int] = mapped_column(Integer, default=0)
    checklist_fully_covered: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- extras written by Agent 1 (not in the original spec; agreed with the team) ---
    duration_sec: Mapped[Optional[float]] = mapped_column(Float)
    language: Mapped[Optional[str]] = mapped_column(String)
    raw_asr_json: Mapped[Optional[dict]] = mapped_column(JSON)            # model name, pieces, segments with word timestamps/probabilities
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())