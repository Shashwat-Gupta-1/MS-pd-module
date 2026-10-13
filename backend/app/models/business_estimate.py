import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class BusinessEstimate(Base):
    __tablename__ = "business_estimates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, unique=True, index=True)
    estimated_stock_value = Column(Float, nullable=False, default=0.0)
    estimated_machinery_value = Column(Float, nullable=False, default=0.0)
    total_physical_assets_min = Column(Float, nullable=False, default=0.0)
    total_physical_assets_max = Column(Float, nullable=False, default=0.0)
    activity_level = Column(String(50), nullable=True, default="medium")
    consistency_with_declared_income = Column(String(50), nullable=True, default="MATCH")
    justification = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(timezone.utc))

    application = relationship("Application", backref="business_estimate", uselist=False)
