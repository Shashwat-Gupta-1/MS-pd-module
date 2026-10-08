"""Application management routes: create/upsert applications in PostgreSQL and fetch application details."""
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.application import Application

router = APIRouter(prefix="/applications", tags=["Applications"])


class ApplicationCreateSchema(BaseModel):
    id: Optional[str] = None
    borrower_name: Optional[str] = None
    product_type: Optional[str] = None
    requested_amount: Optional[float] = 500000.0
    tenure_months: Optional[int] = 36


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_or_update_application(
    payload: ApplicationCreateSchema,
    db: Session = Depends(get_db),
):
    """Create or update a loan application record in PostgreSQL."""
    app_id = payload.id or f"APP-2026-{uuid.uuid4().hex[:4].upper()}"

    app_obj = db.query(Application).filter_by(id=app_id).first()
    if not app_obj:
        app_obj = Application(
            id=app_id,
            borrower_name=payload.borrower_name or "Borrower",
            product_type=payload.product_type or "Business Loan",
            requested_amount=payload.requested_amount,
            tenure_months=payload.tenure_months,
            status="PD_IN_PROGRESS",
        )
        db.add(app_obj)
    else:
        if payload.borrower_name is not None:
            app_obj.borrower_name = payload.borrower_name
        if payload.product_type is not None:
            app_obj.product_type = payload.product_type
        if payload.requested_amount is not None:
            app_obj.requested_amount = payload.requested_amount
        if payload.tenure_months is not None:
            app_obj.tenure_months = payload.tenure_months

    db.commit()
    db.refresh(app_obj)

    return {
        "status": "success",
        "message": "Application saved to PostgreSQL",
        "application": {
            "id": app_obj.id,
            "borrower_name": app_obj.borrower_name,
            "product_type": app_obj.product_type,
            "requested_amount": app_obj.requested_amount,
            "tenure_months": app_obj.tenure_months,
            "status": app_obj.status,
            "created_at": app_obj.created_at.isoformat() if app_obj.created_at else None,
        },
    }


@router.get("/{application_id}", response_model=Dict[str, Any])
def get_application_by_id(application_id: str, db: Session = Depends(get_db)):
    """Fetch an application record by ID from PostgreSQL."""
    app_obj = db.query(Application).filter_by(id=application_id).first()
    if not app_obj:
        raise HTTPException(status_code=404, detail=f"Application '{application_id}' not found")

    return {
        "id": app_obj.id,
        "borrower_name": app_obj.borrower_name,
        "product_type": app_obj.product_type,
        "requested_amount": app_obj.requested_amount,
        "tenure_months": app_obj.tenure_months,
        "status": app_obj.status,
        "created_at": app_obj.created_at.isoformat() if app_obj.created_at else None,
    }
