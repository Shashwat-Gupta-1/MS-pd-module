"""Pydantic request/response schemas for photo_extraction and Agent 3 vision analysis."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DetectedItem(BaseModel):
    name: str = Field(..., description="Name of the physical asset or inventory type")
    count: int = Field(1, description="Approximate count visible in the photo")
    condition: str = Field("good", description="Condition: new, good, fair, poor")
    unit_value_min_inr: float = Field(0.0, description="Lower bound of unit value in INR")
    unit_value_max_inr: float = Field(0.0, description="Upper bound of unit value in INR")
    total_value_min_inr: float = Field(0.0, description="Total lower bound in INR")
    total_value_max_inr: float = Field(0.0, description="Total upper bound in INR")


class PhotoExtractionResult(BaseModel):
    photo_id: str
    category_matches_photo: bool
    category_mismatch_reason: Optional[str] = None
    premises_type: Optional[str] = None
    stock_level: Optional[str] = None
    employee_count_visible: int = 0
    customer_activity_visible: Optional[str] = None
    overall_condition: Optional[str] = None
    items: List[DetectedItem] = []
    estimated_total_value_min: float = 0.0
    estimated_total_value_max: float = 0.0
    summary: Optional[str] = None


class AggregatedAssetItem(BaseModel):
    category: str
    item_name: str
    total_count: int
    condition: str
    unit_value_min_inr: float
    unit_value_max_inr: float
    total_value_min_inr: float
    total_value_max_inr: float
    confidence_score: float = 0.8
    source_photo_ids: List[str] = []


class ApplicationVisionSummary(BaseModel):
    application_id: str
    total_photos_uploaded: int
    all_mandatory_categories_covered: bool
    missing_categories: List[str] = []
    total_asset_value_min_inr: float = 0.0
    total_asset_value_max_inr: float = 0.0
    estimated_monthly_turnover_min_inr: Optional[float] = None
    estimated_monthly_turnover_max_inr: Optional[float] = None
    income_consistency: str = "MATCH"
    audit_flags: List[str] = []
    assets: List[AggregatedAssetItem] = []
    photos: List[Dict[str, Any]] = []
