import uuid
from typing import Any
from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, synonym
from app.core.database import Base


class OfficerRemark(Base):
    __tablename__ = "officer_remarks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pd_session_id = Column(String(36), ForeignKey("pd_sessions.id"), nullable=False, index=True)
    flag_reference_id = Column(String(36), nullable=True)  # links to customer_consistency_flag or gap_question
    structured_response = Column(Text, nullable=True)  # Officer's structured assessment of a flag
    open_remark_text = Column(Text, nullable=True)  # Free-text field for qualitative observations
    remark_text = synonym("open_remark_text")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    pd_session = relationship("PDSession", backref="remarks")

    def __init__(self, **kwargs: Any) -> None:
        if "remark_text" in kwargs and "open_remark_text" not in kwargs:
            kwargs["open_remark_text"] = kwargs.pop("remark_text")
        super().__init__(**kwargs)
