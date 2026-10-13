import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class OfficerPDScore(Base):
    __tablename__ = "officer_pd_scores"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pd_session_id = Column(String(36), ForeignKey("pd_sessions.id"), nullable=False, index=True)
    officer_id = Column(String(36), ForeignKey("officers.id"), nullable=False, index=True)
    coverage_score = Column(Float, nullable=False)  # % of mandatory checklist captured
    suggestion_uptake_score = Column(Float, nullable=False)  # % of AI gap questions asked
    reconfirmation_diligence_score = Column(Float, nullable=False)  # photo diligence & numeric reconfirmation
    proactive_diligence_bonus = Column(Float, nullable=False, default=0.0)  # separate proactive diligence bonus points
    overall_score = Column(Float, nullable=False)  # weighted combined score (underwriter-only)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pd_session = relationship("PDSession", backref="scores")
    officer = relationship("Officer", backref="scores")
