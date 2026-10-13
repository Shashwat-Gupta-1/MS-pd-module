from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class BREPreliminaryCalcBase(BaseModel):
    emi_calculated: float = Field(..., ge=0, description="Monthly EMI calculated via reducing balance")
    foir_pct: float = Field(..., ge=0, description="Fixed Obligation to Income Ratio %")
    ltv_pct: Optional[float] = Field(None, ge=0, description="Loan-to-Value %")
    ltv_status: Literal["computed", "not_applicable", "pending_collateral_valuation"]


class BREPreliminaryCalcCreate(BREPreliminaryCalcBase):
    application_id: str


class BREPreliminaryCalcResponse(BREPreliminaryCalcBase):
    id: str
    application_id: str
    computed_at: datetime

    model_config = ConfigDict(from_attributes=True)
