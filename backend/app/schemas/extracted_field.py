from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class ExtractedFieldBase(BaseModel):
    field_name: str
    value: Optional[str] = None
    source: Literal["stated", "inferred", "not_captured"]
    confidence_note: Optional[str] = None
    officer_confirmed: bool = False


class ExtractedFieldCreate(ExtractedFieldBase):
    pd_session_id: str


class FieldReconfirmRequest(BaseModel):
    confirmed_value: Optional[str] = Field(None, description="Corrected value if borrower clarified")
    officer_confirmed: bool = Field(True, description="Flag indicating officer confirmed out loud")


class ExtractedFieldResponse(ExtractedFieldBase):
    id: str
    pd_session_id: str

    model_config = ConfigDict(from_attributes=True)
