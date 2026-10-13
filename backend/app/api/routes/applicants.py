from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_officer
from app.models.applicant import Applicant
from app.models.officer import Officer
from app.schemas.applicant import ApplicantCreate, ApplicantResponse, ApplicantUpdate

router = APIRouter()


@router.post("", response_model=ApplicantResponse, status_code=status.HTTP_201_CREATED, summary="Create and de-duplicate applicant profile")
@router.post("/", response_model=ApplicantResponse, status_code=status.HTTP_201_CREATED, summary="Create and de-duplicate applicant profile")
def create_applicant(
    data: ApplicantCreate,
    upsert: bool = Query(False, description="If true, update existing applicant if phone or PAN already exists"),
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    # De-duplicate by phone
    existing_phone = db.query(Applicant).filter(Applicant.phone == data.phone).first()
    if existing_phone:
        if upsert:
            existing_phone.name = data.name
            existing_phone.employment_type = data.employment_type
            existing_phone.business_category = data.business_category
            existing_phone.employer_type = data.employer_type
            if data.pan:
                existing_phone.pan = data.pan.upper()
            if data.aadhaar_number:
                existing_phone.aadhaar_number = data.aadhaar_number
            db.commit()
            db.refresh(existing_phone)
            return existing_phone
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An applicant with phone {data.phone} already exists (ID: {existing_phone.id})"
        )

    # De-duplicate by PAN if provided
    if data.pan:
        existing_pan = db.query(Applicant).filter(Applicant.pan == data.pan.upper()).first()
        if existing_pan:
            if upsert:
                existing_pan.name = data.name
                existing_pan.phone = data.phone
                existing_pan.employment_type = data.employment_type
                existing_pan.business_category = data.business_category
                existing_pan.employer_type = data.employer_type
                if data.aadhaar_number:
                    existing_pan.aadhaar_number = data.aadhaar_number
                db.commit()
                db.refresh(existing_pan)
                return existing_pan
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An applicant with PAN {data.pan} already exists (ID: {existing_pan.id})"
            )

    applicant = Applicant(
        name=data.name,
        phone=data.phone,
        pan=data.pan.upper() if data.pan else None,
        aadhaar_number=data.aadhaar_number,
        employment_type=data.employment_type,
        business_category=data.business_category,
        employer_type=data.employer_type,
    )
    db.add(applicant)
    db.commit()
    db.refresh(applicant)
    return applicant


@router.get("/{id}", response_model=ApplicantResponse, summary="Get applicant by ID")
def get_applicant(
    id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    applicant = db.query(Applicant).filter(Applicant.id == id).first()
    if not applicant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant not found")
    return applicant


@router.get("/", response_model=List[ApplicantResponse], summary="List or search applicants")
def list_applicants(
    phone: Optional[str] = Query(None, description="Search by exact or partial phone"),
    name: Optional[str] = Query(None, description="Search by name"),
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    query = db.query(Applicant)
    if phone:
        query = query.filter(Applicant.phone.contains(phone))
    if name:
        query = query.filter(Applicant.name.ilike(f"%{name}%"))
    return query.order_by(Applicant.created_at.desc()).limit(100).all()
