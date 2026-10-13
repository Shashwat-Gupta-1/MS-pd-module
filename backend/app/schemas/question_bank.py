from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


class QuestionBankBase(BaseModel):
    tier: Literal[1, 2, 3] = Field(..., description="Tier 1 Universal, Tier 2 Branch, Tier 3 Specific Category")
    employment_type: Optional[str] = None  # self_employed | salaried | all
    business_category: Optional[str] = None
    question_text: str = Field(..., min_length=5, max_length=500)
    field_name: str = Field(..., min_length=2, max_length=100)
    data_type: str = Field("text", description="text | number | boolean | select")
    is_mandatory: bool = True


class QuestionBankCreate(QuestionBankBase):
    pass


class QuestionBankResponse(QuestionBankBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
