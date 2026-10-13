import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import Column, String, Float, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class GroundPDPhoto(Base):
    __tablename__ = "ground_pd_photos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=True, index=True)
    pd_session_id = Column(String(36), ForeignKey("pd_sessions.id"), nullable=True, index=True)
    category = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    accuracy_radius = Column(Float, nullable=True)  # Accuracy radius in meters
    captured_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Audit & Verification metadata
    phash = Column(String(64), nullable=True, index=True)
    device_model = Column(String(100), nullable=True)
    exif_captured_at = Column(DateTime(timezone=True), nullable=True)
    is_live_capture = Column(Boolean, nullable=True, default=True)
    gps_accuracy_status = Column(String(50), nullable=True)
    site_distance_meters = Column(Float, nullable=True)
    flags = Column(JSON, nullable=True, default=list)

    application = relationship("Application", backref="photos")
    pd_session = relationship("PDSession", backref="photos")

    def __init__(self, **kwargs: Any) -> None:
        if "photo_category" in kwargs and "category" not in kwargs:
            kwargs["category"] = kwargs.pop("photo_category")
        if "file_path" in kwargs and "url" not in kwargs:
            kwargs["url"] = kwargs.pop("file_path")
        if "gps_latitude" in kwargs and "lat" not in kwargs:
            kwargs["lat"] = kwargs.pop("gps_latitude")
        if "gps_longitude" in kwargs and "lng" not in kwargs:
            kwargs["lng"] = kwargs.pop("gps_longitude")
        if "captured_at" not in kwargs:
            kwargs["captured_at"] = datetime.now(timezone.utc)
        super().__init__(**kwargs)

    @property
    def photo_category(self) -> str:
        return self.category

    @photo_category.setter
    def photo_category(self, value: str) -> None:
        self.category = value

    @property
    def file_path(self) -> str:
        return self.url

    @file_path.setter
    def file_path(self, value: str) -> None:
        self.url = value

    @property
    def gps_latitude(self) -> float:
        return self.lat

    @gps_latitude.setter
    def gps_latitude(self, value: float) -> None:
        self.lat = value

    @property
    def gps_longitude(self) -> float:
        return self.lng

    @gps_longitude.setter
    def gps_longitude(self, value: float) -> None:
        self.lng = value
