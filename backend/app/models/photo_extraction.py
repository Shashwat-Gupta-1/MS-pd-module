"""PhotoExtraction model: photo_id FK, structured output of the Gemini Vision agent.
Fixed fields + detected items array + estimated value ranges + consistency check.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PhotoExtraction(Base):
    __tablename__ = "photo_extractions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    photo_id: Mapped[str] = mapped_column(ForeignKey("ground_pd_photos.id", ondelete="CASCADE"), unique=True, index=True)

    # Gemini Vision extracted fields
    category_matches_photo: Mapped[bool] = mapped_column(Boolean, default=True)
    category_mismatch_reason: Mapped[Optional[str]] = mapped_column(Text)

    premises_type: Mapped[Optional[str]] = mapped_column(String)       # e.g., "retail_shop", "industrial_shed", "residential"
    stock_level: Mapped[Optional[str]] = mapped_column(String)         # empty, low, medium, high, overstocked
    employee_count_visible: Mapped[int] = mapped_column(Integer, default=0)
    customer_activity_visible: Mapped[Optional[str]] = mapped_column(String) # low, medium, high, none
    overall_condition: Mapped[Optional[str]] = mapped_column(String)   # excellent, good, fair, poor

    # Detected physical assets list: [{"name": "...", "count": 2, "condition": "good", "est_unit_val_min": 50000, "est_unit_val_max": 75000}]
    items: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Valuation bounds estimated for this photo
    estimated_total_value_min: Mapped[Optional[float]] = mapped_column(Float)
    estimated_total_value_max: Mapped[Optional[float]] = mapped_column(Float)

    # Raw LLM output & summary
    summary: Mapped[Optional[str]] = mapped_column(Text)
    raw_llm_json: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship back to GroundPDPhoto
    photo: Mapped["GroundPDPhoto"] = relationship("GroundPDPhoto", back_populates="extraction")
