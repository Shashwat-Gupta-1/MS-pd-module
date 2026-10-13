from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class GapQuestionBase(BaseModel):
    question_text: str
    category: Optional[str] = None
    round_number: int = 1
    resolved: bool = False
    answer: Optional[str] = None
    override_reason: Optional[str] = None


class GapQuestionCreate(GapQuestionBase):
    pd_session_id: str


class GapResolveRequest(BaseModel):
    answer: Optional[str] = Field(None, description="Borrower response to the question")
    resolved: bool = Field(True, description="Whether this gap question is now resolved")
    override_reason: Optional[str] = Field(None, description="Reason if question was skipped (e.g. Already covered, Not applicable)")


class GapQuestionResponse(GapQuestionBase):
    id: str
    pd_session_id: str

    model_config = ConfigDict(from_attributes=True)
