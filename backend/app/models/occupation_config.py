import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON
from app.core.database import Base


class OccupationConfig(Base):
    __tablename__ = "occupation_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    occupation_name = Column(String(100), nullable=False, unique=True, index=True)
    category_hints = Column(Text, nullable=True)
    valuation_guide = Column(Text, nullable=True)
    typical_assets = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
