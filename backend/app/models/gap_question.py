import uuid
from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class GapQuestion(Base):
    __tablename__ = "gap_questions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pd_session_id = Column(String(36), ForeignKey("pd_sessions.id"), nullable=False, index=True)
    question_text = Column(String(500), nullable=False)
    category = Column(String(100), nullable=True)
    round_number = Column(Integer, nullable=False, default=1)
    resolved = Column(Boolean, nullable=False, default=False)
    answer = Column(Text, nullable=True)
    override_reason = Column(Text, nullable=True)  # Reason if explicitly skipped by officer

    pd_session = relationship("PDSession", backref="gap_questions")
