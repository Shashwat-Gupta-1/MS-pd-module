"""TranscriptSegment model: pd_session_id FK, start_time, end_time, text, confidence. One row per Whisper output segment."""
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (UniqueConstraint("pd_session_id", "seq", name="uq_segment_session_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pd_session_id: Mapped[str] = mapped_column(ForeignKey("pd_sessions.id"), index=True)
    start_time: Mapped[float] = mapped_column(Float)                      # seconds from start of recording
    end_time: Mapped[float] = mapped_column(Float)                        # seconds
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)                      # 0..1, mean word probability

    # --- extras written by Agent 1 (agreed with the team) ---
    seq: Mapped[int] = mapped_column(Integer)                             # order within the session
    speaker: Mapped[str] = mapped_column(String)                          # officer | borrower | unknown
    min_word_conf: Mapped[Optional[float]] = mapped_column(Float)         # weakest word, for numeric reconfirmation
    low_confidence: Mapped[bool] = mapped_column(Boolean, default=False)