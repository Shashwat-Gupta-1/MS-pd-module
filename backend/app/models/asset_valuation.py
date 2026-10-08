"""AssetValuation model: stores aggregated physical asset inventory and valuation range per application."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AssetValuation(Base):
    __tablename__ = "asset_valuations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)

    category: Mapped[str] = mapped_column(String)  # e.g., "machinery", "stock_inventory", "cattle", "vehicles"
    item_name: Mapped[str] = mapped_column(String)
    total_count: Mapped[int] = mapped_column(Integer, default=1)
    condition: Mapped[str] = mapped_column(String, default="good")

    unit_value_min_inr: Mapped[float] = mapped_column(Float, default=0.0)
    unit_value_max_inr: Mapped[float] = mapped_column(Float, default=0.0)

    total_value_min_inr: Mapped[float] = mapped_column(Float, default=0.0)
    total_value_max_inr: Mapped[float] = mapped_column(Float, default=0.0)

    confidence_score: Mapped[float] = mapped_column(Float, default=0.8)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    source_photo_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
