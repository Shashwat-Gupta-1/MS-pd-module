from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PhotoExtractionBase(BaseModel):
    machinery_type: Optional[str] = Field(None, description="Identified equipment/machinery type")
    approx_count: Optional[int] = Field(None, ge=0, description="Approximate count of machinery")
    employee_count_visible: Optional[int] = Field(None, ge=0, description="Visible workers count")
    condition: Optional[str] = Field(None, description="Operational state (e.g. good, operational, idle)")


class PhotoExtractionCreate(PhotoExtractionBase):
    photo_id: str


class PhotoExtractionResponse(PhotoExtractionBase):
    id: str
    photo_id: str

    model_config = ConfigDict(from_attributes=True)
