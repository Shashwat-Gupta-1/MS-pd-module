"""GroundPDPhoto model: application_id FK, category, storage_path, lat, lng, accuracy_radius, captured_at.
GPS and EXIF are captured per-photo. Stores perceptual hash, duplicate status, and live-capture verification.
"""
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class GroundPDPhoto(Base):
    __tablename__ = "ground_pd_photos"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    category: Mapped[str] = mapped_column(String, index=True) # e.g. "business_machinery", "stock", "collateral"
    
    file_name: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Float)
    mime_type: Mapped[str] = mapped_column(String, default="image/jpeg")

    # GPS data
    lat: Mapped[Optional[float]] = mapped_column(Float)
    lng: Mapped[Optional[float]] = mapped_column(Float)
    accuracy_m: Mapped[Optional[float]] = mapped_column(Float)
    gps_status: Mapped[str] = mapped_column(String, default="UNKNOWN")  # VALID, POOR_ACCURACY, DISTANCE_MISMATCH, NO_GPS
    distance_to_site_m: Mapped[Optional[float]] = mapped_column(Float)

    # Live Camera & EXIF verification
    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_live_capture: Mapped[bool] = mapped_column(Boolean, default=True)
    device_model: Mapped[Optional[str]] = mapped_column(String)

    # Duplicate detection
    phash: Mapped[Optional[str]] = mapped_column(String, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Risk & Audit flags
    flags: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Relationships
    extraction: Mapped[Optional["PhotoExtraction"]] = relationship(
        "PhotoExtraction",
        back_populates="photo",
        uselist=False,
        cascade="all, delete-orphan",
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
