from typing import Any
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship, synonym
from app.core.database import Base


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pd_session_id = Column(String(36), ForeignKey("pd_sessions.id"), nullable=False, index=True)
    session_id = synonym("pd_session_id")
    seq = Column(Integer, nullable=True, default=0)
    start_time = Column(Float, nullable=False)  # in seconds from start of audio
    end_time = Column(Float, nullable=False)
    speaker = Column(String(50), nullable=True)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=1.0)  # 0.0 to 1.0 from faster-whisper
    min_word_conf = Column(Float, nullable=True)
    low_confidence = Column(Boolean, nullable=True, default=False)

    pd_session = relationship("PDSession", backref="transcript_segments")

    def __init__(self, **kwargs: Any) -> None:
        if "session_id" in kwargs and "pd_session_id" not in kwargs:
            kwargs["pd_session_id"] = kwargs.pop("session_id")
        super().__init__(**kwargs)
