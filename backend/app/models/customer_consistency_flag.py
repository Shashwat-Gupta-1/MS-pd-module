import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class CustomerConsistencyFlag(Base):
    __tablename__ = "customer_consistency_flags"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pd_session_id = Column(String(36), ForeignKey("pd_sessions.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    value_a = Column(Text, nullable=False)
    value_a_timestamp = Column(String(50), nullable=True)  # Audio offset or segment reference
    value_b = Column(Text, nullable=False)
    value_b_timestamp = Column(String(50), nullable=True)
    severity = Column(String(20), nullable=False, default="medium")  # low | medium | high
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pd_session = relationship("PDSession", backref="consistency_flags")
