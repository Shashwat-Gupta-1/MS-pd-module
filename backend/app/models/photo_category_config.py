import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime
from app.core.database import Base


class PhotoCategoryConfig(Base):
    __tablename__ = "photo_category_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    category_hints = Column(Text, nullable=True)
    valuation_guide = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
