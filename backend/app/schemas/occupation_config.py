"""Pydantic schemas for occupation and category configurations."""
from typing import List, Optional
from pydantic import BaseModel, Field


class PhotoCategoryConfigSchema(BaseModel):
    id: Optional[str] = None
    category_code: str
    label: str
    description: Optional[str] = None
    is_mandatory: bool = True
    min_photos: int = 1
    max_photos: int = 5
    prompt_hints: Optional[str] = None
    valuation_guide: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class OccupationConfigSchema(BaseModel):
    id: Optional[str] = None
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True
    categories: List[PhotoCategoryConfigSchema] = []

    class Config:
        from_attributes = True
