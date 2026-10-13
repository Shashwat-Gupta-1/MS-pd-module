import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship, backref
from app.core.database import Base


class PhotoExtraction(Base):
    __tablename__ = "photo_extractions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    photo_id = Column(String(36), ForeignKey("ground_pd_photos.id"), nullable=False, index=True)

    # Legacy fields
    machinery_type = Column(String(200), nullable=True)
    approx_count = Column(Integer, nullable=True)
    condition = Column(String(100), nullable=True)

    # Agent 3: Vision Extraction structured fields
    category_matches_photo = Column(Boolean, nullable=True, default=True)
    category_mismatch_reason = Column(Text, nullable=True)
    premises_type = Column(String(100), nullable=True)
    stock_level = Column(String(50), nullable=True)
    employee_count_visible = Column(Integer, nullable=True, default=0)
    customer_activity_visible = Column(String(50), nullable=True)
    overall_condition = Column(String(50), nullable=True)
    items = Column(JSON, nullable=True, default=list)
    estimated_total_value_min = Column(Float, nullable=True, default=0.0)
    estimated_total_value_max = Column(Float, nullable=True, default=0.0)
    summary = Column(Text, nullable=True)
    raw_extraction = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # 1:1 relationship with GroundPDPhoto allowing p.extraction access
    photo = relationship("GroundPDPhoto", backref=backref("extraction", uselist=False))
