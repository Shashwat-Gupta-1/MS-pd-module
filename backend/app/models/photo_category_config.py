"""PhotoCategoryConfig model: defines mandatory photos, min/max count, and LLM prompt hints per occupation."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PhotoCategoryConfig(Base):
    __tablename__ = "photo_category_configs"
    __table_args__ = (
        UniqueConstraint("occupation_id", "category_code", name="uq_occupation_category"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    occupation_id: Mapped[str] = mapped_column(ForeignKey("occupation_configs.id", ondelete="CASCADE"), index=True)
    
    category_code: Mapped[str] = mapped_column(String, nullable=False)   # e.g., "shelf_inventory", "cattle_shed"
    label: Mapped[str] = mapped_column(String, nullable=False)           # e.g., "Shelf Stock & Inventory"
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    min_photos: Mapped[int] = mapped_column(Integer, default=1)
    max_photos: Mapped[int] = mapped_column(Integer, default=5)
    
    # Prompt hints injected dynamically into Gemini Vision instructions
    prompt_hints: Mapped[Optional[str]] = mapped_column(Text)           # e.g., "Look for branded FMCG stock, count shelves, check expiry tags"
    valuation_guide: Mapped[Optional[str]] = mapped_column(Text)        # e.g., "Kirana inventory typically INR 50k to 5L based on shelf density"
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    occupation: Mapped["OccupationConfig"] = relationship("OccupationConfig", back_populates="categories")
