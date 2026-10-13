from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class CustomerConsistencyFlagBase(BaseModel):
    field_name: str
    value_a: str = Field(..., description="First stated value")
    value_a_timestamp: Optional[str] = Field(None, description="Timestamp/offset of first value")
    value_b: str = Field(..., description="Contradicting later value")
    value_b_timestamp: Optional[str] = Field(None, description="Timestamp/offset of conflicting value")
    severity: Literal["low", "medium", "high"] = "medium"
    resolution_note: Optional[str] = None


class CustomerConsistencyFlagCreate(CustomerConsistencyFlagBase):
    pd_session_id: str


class ConsistencyResolveRequest(BaseModel):
    resolution_note: str = Field(..., min_length=5, description="Officer's on-the-spot resolution explanation")


class CustomerConsistencyFlagResponse(CustomerConsistencyFlagBase):
    id: str
    pd_session_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
