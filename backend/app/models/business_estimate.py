"""BusinessEstimate model: stores visual-derived operational scale, monthly revenue/expense estimates from photos."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BusinessEstimate(Base):
    __tablename__ = "business_estimates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), unique=True, index=True)

    declared_monthly_turnover: Mapped[Optional[float]] = mapped_column(Float)
    estimated_monthly_turnover_min: Mapped[Optional[float]] = mapped_column(Float)
    estimated_monthly_turnover_max: Mapped[Optional[float]] = mapped_column(Float)

    estimated_stock_value: Mapped[Optional[float]] = mapped_column(Float)
    estimated_machinery_value: Mapped[Optional[float]] = mapped_column(Float)
    total_physical_assets_min: Mapped[Optional[float]] = mapped_column(Float)
    total_physical_assets_max: Mapped[Optional[float]] = mapped_column(Float)

    activity_level: Mapped[Optional[str]] = mapped_column(String) # low, medium, high
    consistency_with_declared_income: Mapped[str] = mapped_column(String, default="MATCH") # MATCH, OVERSTATED_INCOME, UNDERSTATED_INCOME, INSUFFICIENT_DATA
    justification: Mapped[Optional[str]] = mapped_column(Text)
    evidence_breakdown: Mapped[Optional[dict]] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
