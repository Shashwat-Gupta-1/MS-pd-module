from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_officer
from app.core.security import verify_password, hash_password, create_access_token, generate_otp, verify_otp
from app.models.officer import Officer
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    OTPVerifyRequest,
    OfficerResponse,
    OfficerCreateRequest,
)

router = APIRouter()


def _clean_phone(phone_raw: str) -> str:
    cleaned = "".join(filter(str.isdigit, str(phone_raw).strip()))
    if len(cleaned) > 10 and cleaned.startswith("91"):
        cleaned = cleaned[-10:]
    return cleaned


def _ensure_default_officers(db: Session) -> None:
    """Auto-seed default officer and admin accounts if database is empty."""
    if db.query(Officer).count() == 0:
        demo_officer = Officer(
            name="Demo Field Officer",
            phone="9876543210",
            role="officer",
            branch="Jaipur Central",
            hashed_password=hash_password("password123"),
        )
        demo_admin = Officer(
            name="Admin Quality Reviewer",
            phone="9999999999",
            role="admin",
            branch="Head Office",
            hashed_password=hash_password("admin123"),
        )
        db.add_all([demo_officer, demo_admin])
        db.commit()


@router.post("/login", response_model=TokenResponse, summary="Officer or Admin Login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    _ensure_default_officers(db)
    
    clean_phone = _clean_phone(request.phone)
    officer = db.query(Officer).filter(
        (Officer.phone == clean_phone) | (Officer.phone == request.phone.strip())
    ).first()
    if not officer or not verify_password(request.password, officer.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mobile number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": officer.id, "role": officer.role, "name": officer.name}
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=officer.role,
        officer_id=officer.id,
        name=officer.name,
    )


@router.post("/register", response_model=OfficerResponse, status_code=status.HTTP_201_CREATED, summary="Register or add a new officer")
@router.post("/officers", response_model=OfficerResponse, status_code=status.HTTP_201_CREATED, summary="Add a new officer")
def register_officer(request: OfficerCreateRequest, db: Session = Depends(get_db)):
    _ensure_default_officers(db)

    clean_phone = _clean_phone(request.phone)
    if len(clean_phone) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid 10-digit mobile number."
        )

    existing = db.query(Officer).filter(
        (Officer.phone == clean_phone) | (Officer.phone == request.phone.strip())
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Officer with mobile number {clean_phone} already exists."
        )

    new_officer = Officer(
        name=request.name.strip(),
        phone=clean_phone,
        role=request.role.strip().lower() if request.role else "officer",
        branch=request.branch.strip() if request.branch else "Jaipur Central",
        hashed_password=hash_password(request.password),
    )
    db.add(new_officer)
    db.commit()
    db.refresh(new_officer)
    return new_officer


@router.get("/officers", response_model=List[OfficerResponse], summary="List all registered officers")
def list_officers(db: Session = Depends(get_db)):
    _ensure_default_officers(db)
    return db.query(Officer).order_by(Officer.created_at.desc()).all()


@router.post("/send-otp", summary="Send applicant verification OTP")
def send_otp(phone: str):
    otp = generate_otp(phone)
    return {
        "status": "sent",
        "phone": phone,
        "message": f"OTP sent successfully (Simulated dev OTP: {otp})"
    }


@router.post("/verify-otp", summary="Verify applicant mobile OTP")
def verify_applicant_otp(request: OTPVerifyRequest):
    if not verify_otp(request.phone, request.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP"
        )
    return {"status": "verified", "phone": request.phone}


@router.get("/me", response_model=OfficerResponse, summary="Get current logged in officer profile")
def get_me(current_officer: Officer = Depends(get_current_officer)):
    return current_officer

