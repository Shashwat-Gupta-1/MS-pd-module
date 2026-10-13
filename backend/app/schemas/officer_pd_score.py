from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class OfficerPDScoreBase(BaseModel):
    coverage_score: float = Field(..., ge=0, le=100, description="Percentage of mandatory items captured")
    suggestion_uptake_score: float = Field(..., ge=0, le=100, description="Percentage of AI suggestions asked")
    reconfirmation_diligence_score: float = Field(..., ge=0, le=100, description="Diligence on flagged numerics and inconsistency notes")
    proactive_diligence_bonus: float = Field(0.0, ge=0, description="Separate proactive diligence bonus points")
    overall_score: float = Field(..., ge=0, le=100, description="Weighted composite score (internal underwriter only)")


class OfficerPDScoreCreate(OfficerPDScoreBase):
    pd_session_id: str
    officer_id: str


class OfficerPDScoreResponse(OfficerPDScoreBase):
    id: str
    pd_session_id: str
    officer_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
