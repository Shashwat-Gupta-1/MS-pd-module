from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class TranscriptSegmentResponse(BaseModel):
    id: int
    seq: Optional[int] = 0
    start_time: float
    end_time: float
    speaker: Optional[str] = "borrower"
    text: str
    confidence: float
    min_word_conf: Optional[float] = None
    low_confidence: Optional[bool] = False

    model_config = ConfigDict(from_attributes=True)


class TranscriptResponse(BaseModel):
    session_id: str
    status: str
    language: Optional[str] = None
    duration_sec: Optional[float] = None
    transcript_raw: Optional[str] = None
    segments: List[TranscriptSegmentResponse] = []


class PDSessionStartRequest(BaseModel):
    application_id: str
    officer_id: Optional[str] = None
    consent_captured: bool = Field(True, description="Borrower consent to record audio")


class PDSessionEndRequest(BaseModel):
    recording_url: Optional[str] = None


class PDSessionResponse(BaseModel):
    id: str
    application_id: str
    officer_id: str
    channel: str = "ground"
    recording_url: Optional[str] = None
    consent_captured: bool
    consent_timestamp: Optional[datetime] = None
    transcript_raw: Optional[str] = None
    status: str
    gap_round_count: int = 0
    checklist_fully_covered: bool = False
    is_session_active: bool = True
    started_at: datetime
    ended_at: Optional[datetime] = None
    transcript_segments: List[TranscriptSegmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BatchTranscriptRequest(BaseModel):
    chunk_sequence: int = 0
    audio_chunk_base64: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None


class ReconfirmFieldRequest(BaseModel):
    field_name: str
    confirmed_value: Optional[str] = None
    officer_confirmed: bool = True


class ManualFieldRequest(BaseModel):
    field_name: str
    value: str
    reason: Optional[str] = "Audio quality fallback"


class RemarksRequest(BaseModel):
    remark_text: str
    consistency_resolutions: Optional[List[Dict[str, str]]] = None


class LiveStateResponse(BaseModel):
    session_id: str
    is_session_active: bool
    active_followup_questions: List[Dict[str, Any]]
    resolved_followup_questions: List[Dict[str, Any]] = []
    extracted_fields: Dict[str, Any]
    gaps_remaining: bool
    officer_uptake_count: int
    officer_proactive_bonus_points: int
    customer_contradiction_count: int


class PDSessionEndResponse(BaseModel):
    session_id: str
    status: str
    completion_gate: Dict[str, Any]
    officer_score: Dict[str, Any]
    consistency_flags_count: int
    report_path: Optional[str] = None
