from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_officer
from app.models.application import Application
from app.models.applicant import Applicant
from app.models.officer import Officer
from app.schemas.application import ApplicationCreate, ApplicationResponse

router = APIRouter()


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED, summary="Create a new loan application")
def create_application(
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    applicant = db.query(Applicant).filter(Applicant.id == data.applicant_id).first()
    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Applicant with ID {data.applicant_id} does not exist"
        )

    application = Application(
        applicant_id=data.applicant_id,
        product_type=data.product_type,
        requested_amount=data.requested_amount,
        tenure=data.tenure,
        rate=data.rate,
        status="INTAKE",
        geo_confirmation_status="insufficient_photos"
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.get("/{id}", response_model=ApplicationResponse, summary="Get loan application detail")
def get_application(
    id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    application = db.query(Application).filter(Application.id == id).first()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.get("/", response_model=List[ApplicationResponse], summary="List or filter loan applications")
def list_applications(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by INTAKE, PD_IN_PROGRESS, PD_COMPLETE"),
    applicant_id: Optional[str] = Query(None, description="Filter by applicant ID"),
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    query = db.query(Application)
    if status_filter:
        query = query.filter(Application.status == status_filter.upper())
    if applicant_id:
        query = query.filter(Application.applicant_id == applicant_id)
    return query.order_by(Application.created_at.desc()).limit(100).all()


@router.post("/{id}/start-pd", response_model=ApplicationResponse, summary="Transition case status to PD_IN_PROGRESS")
def start_pd(
    id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    application = db.query(Application).filter(Application.id == id).first()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    
    application.status = "PD_IN_PROGRESS"
    db.commit()
    db.refresh(application)
    return application
