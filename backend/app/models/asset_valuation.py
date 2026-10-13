import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class AssetValuation(Base):
    __tablename__ = "asset_valuations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    item_name = Column(String(200), nullable=False)
    total_count = Column(Integer, nullable=False, default=1)
    condition = Column(String(50), nullable=True, default="good")
    unit_value_min_inr = Column(Float, nullable=False, default=0.0)
    unit_value_max_inr = Column(Float, nullable=False, default=0.0)
    total_value_min_inr = Column(Float, nullable=False, default=0.0)
    total_value_max_inr = Column(Float, nullable=False, default=0.0)
    source_photo_ids = Column(JSON, nullable=True, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    application = relationship("Application", backref="asset_valuations")
