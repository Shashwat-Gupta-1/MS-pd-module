import uuid
from sqlalchemy import Column, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pd_session_id = Column(String(36), ForeignKey("pd_sessions.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=True)
    source = Column(String(20), nullable=False)  # stated | inferred | not_captured
    confidence_note = Column(Text, nullable=True)
    officer_confirmed = Column(Boolean, nullable=False, default=False)

    pd_session = relationship("PDSession", backref="extracted_fields")
