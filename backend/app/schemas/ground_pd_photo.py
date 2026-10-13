from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GroundPDPhotoBase(BaseModel):
    application_id: str
    category: str = Field(..., description="e.g. premises_front, inventory, machinery, applicant_presence")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude")
    accuracy_radius: Optional[float] = Field(None, ge=0, description="GPS accuracy in meters")
    captured_at: datetime


class GroundPDPhotoCreate(GroundPDPhotoBase):
    url: str


class GroundPDPhotoResponse(GroundPDPhotoCreate):
    id: str

    model_config = ConfigDict(from_attributes=True)
