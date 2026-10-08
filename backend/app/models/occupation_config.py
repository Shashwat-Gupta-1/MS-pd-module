"""OccupationConfig model: stores occupation types and metadata.
Adding an occupation = inserting a row in this table. Zero code changes.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OccupationConfig(Base):
    __tablename__ = "occupation_configs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String, unique=True, index=True)  # e.g., "kirana", "dairy", "garments"
    name: Mapped[str] = mapped_column(String, nullable=False)           # e.g., "Kirana Store / Retail"
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationship to category rules
    categories: Mapped[List["PhotoCategoryConfig"]] = relationship(
        "PhotoCategoryConfig",
        back_populates="occupation",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
