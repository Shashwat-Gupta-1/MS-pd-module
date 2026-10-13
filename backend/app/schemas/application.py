from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.applicant import ApplicantResponse


class ApplicationBase(BaseModel):
    applicant_id: str
    product_type: str = Field(..., description="e.g. LAP, secured_business_loan, retail")
    requested_amount: float = Field(..., gt=0, description="Principal requested loan amount")
    tenure: int = Field(..., gt=0, description="Tenure in months")
    rate: float = Field(..., ge=0, description="Annual interest rate percentage")


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationResponse(ApplicationBase):
    id: str
    status: Literal["INTAKE", "PD_IN_PROGRESS", "PD_COMPLETE"]
    geo_confirmation_status: Literal["confirmed", "flagged", "insufficient_photos"]
    created_at: datetime
    applicant: Optional[ApplicantResponse] = None

    model_config = ConfigDict(from_attributes=True)
