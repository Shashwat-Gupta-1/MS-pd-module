"""Application model: id, borrower_name, product_type, requested_amount, tenure, status."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    borrower_name: Mapped[Optional[str]] = mapped_column(String)
    product_type: Mapped[Optional[str]] = mapped_column(String)
    requested_amount: Mapped[Optional[float]] = mapped_column(Float)
    tenure_months: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="PD_IN_PROGRESS")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
