import re
from datetime import datetime
from typing import Optional, Literal, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., description="E.164 or 10-digit mobile number")
    pan: Optional[str] = Field(None, description="Valid Indian PAN")
    aadhaar_number: Optional[str] = Field(None, description="Aadhaar number or last 4 digits")
    employment_type: str = Field(..., description="self_employed or salaried")
    business_category: Optional[str] = None
    employer_type: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, v: Any) -> str:
        s = str(v or "").strip()
        return s if len(s) >= 2 else "Applicant"

    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, v: Any) -> str:
        s = re.sub(r"[^\d+]", "", str(v or "").strip())
        if not s or len(s) < 10:
            return "9876543210"
        return s

    @field_validator("pan", mode="before")
    @classmethod
    def clean_pan(cls, v: Any) -> Optional[str]:
        if not v:
            return None
        s = str(v).strip().upper()
        return s if s else None

    @field_validator("employment_type", mode="before")
    @classmethod
    def clean_employment_type(cls, v: Any) -> str:
        s = str(v or "").strip().lower()
        if "salari" in s:
            return "salaried"
        return "self_employed"


class ApplicantCreate(ApplicantBase):
    pass


class ApplicantUpdate(BaseModel):
    name: Optional[str] = None
    pan: Optional[str] = None
    aadhaar_number: Optional[str] = None
    business_category: Optional[str] = None
    employer_type: Optional[str] = None


class ApplicantResponse(ApplicantBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
