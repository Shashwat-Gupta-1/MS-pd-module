from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class OfficerRemarkBase(BaseModel):
    flag_reference_id: Optional[str] = Field(None, description="Linked consistency flag or gap question ID")
    structured_response: Optional[str] = Field(None, description="Assessment regarding specific system flag")
    open_remark_text: Optional[str] = Field(None, description="Open-ended qualitative observation")


class OfficerRemarkCreate(OfficerRemarkBase):
    pd_session_id: str


class OfficerRemarkResponse(OfficerRemarkBase):
    id: str
    pd_session_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
