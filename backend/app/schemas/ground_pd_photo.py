"""Pydantic request/response schemas for ground_pd_photo.
Mirrors the SQLAlchemy model in models/ground_pd_photo.py, used for API validation and serialization.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class PhotoUploadMetadata(BaseModel):
    application_id: str
    category: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy_m: Optional[float] = None
    captured_at: Optional[datetime] = None
    device_model: Optional[str] = None
    site_lat: Optional[float] = None
    site_lng: Optional[float] = None


class PhotoResponse(BaseModel):
    id: str
    application_id: str
    category: str
    file_name: str
    storage_path: str
    mime_type: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    accuracy_m: Optional[float] = None
    gps_status: str
    distance_to_site_m: Optional[float] = None
    is_live_capture: bool
    is_duplicate: bool
    duplicate_of_id: Optional[str] = None
    flags: List[str] = []
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
