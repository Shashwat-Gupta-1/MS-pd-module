import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_db, require_role, get_current_officer
from app.models.officer import Officer
from app.models.officer_pd_score import OfficerPDScore
from app.models.customer_consistency_flag import CustomerConsistencyFlag
from app.models.application import Application, ApplicationStatusEnum
from app.schemas.auth import OfficerCreateRequest, OfficerResponse
from app.core.security import hash_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


def _clean_phone(phone_raw: str) -> str:
    cleaned = "".join(filter(str.isdigit, str(phone_raw).strip()))
    if len(cleaned) > 10 and cleaned.startswith("91"):
        cleaned = cleaned[-10:]
    return cleaned


@router.get("/officers", response_model=List[OfficerResponse], summary="List all officers")
def get_all_officers(
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    """Returns all officers registered in the system."""
    return db.query(Officer).order_by(Officer.created_at.desc()).all()


@router.post("/officers", response_model=OfficerResponse, status_code=status.HTTP_201_CREATED, summary="Create a new officer")
def create_officer(
    request: OfficerCreateRequest,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    """Admin endpoint to create/onboard a new field officer or admin."""
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
            detail=f"An officer with mobile number {clean_phone} already exists."
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



@router.get("/analytics/officer-scores")
@router.get("/officer-scores")
@router.get("/scores")
def get_officer_score_analytics(
    officer_id: Optional[str] = Query(None, description="Filter trends by officer ID"),
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
) -> Dict[str, Any]:
    """
    Returns OfficerPDScore trends, filterable by officer (Section 12).
    """
    query = db.query(OfficerPDScore)
    if officer_id:
        query = query.filter(OfficerPDScore.officer_id == officer_id)

    scores = query.all()
    count = len(scores)

    if count == 0:
        return {
            "total_evaluations": 0,
            "average_coverage_score": 0.0,
            "average_uptake_score": 0.0,
            "average_overall_score": 0.0,
            "scores": []
        }

    avg_cov = sum(s.coverage_score for s in scores) / count
    avg_uptake = sum(s.suggestion_uptake_score for s in scores) / count
    avg_overall = sum(s.overall_score for s in scores) / count

    return {
        "total_evaluations": count,
        "average_coverage_score": round(avg_cov, 2),
        "average_uptake_score": round(avg_uptake, 2),
        "average_overall_score": round(avg_overall, 2),
        "scores": [
            {
                "id": s.id,
                "session_id": s.pd_session_id,
                "officer_id": s.officer_id,
                "coverage_score": s.coverage_score,
                "suggestion_uptake_score": s.suggestion_uptake_score,
                "reconfirmation_diligence_score": s.reconfirmation_diligence_score,
                "proactive_diligence_bonus": s.proactive_diligence_bonus,
                "overall_score": s.overall_score,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in scores
        ]
    }


@router.get("/analytics/consistency-flags")
@router.get("/consistency-flags")
def get_consistency_flag_analytics(
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high"),
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
) -> Dict[str, Any]:
    """
    Returns CustomerConsistencyFlag portfolio-wide trends and distributions (Section 12).
    """
    query = db.query(CustomerConsistencyFlag)
    if severity:
        query = query.filter(CustomerConsistencyFlag.severity == severity.lower())

    flags = query.all()

    severity_counts = {"low": 0, "medium": 0, "high": 0}
    field_counts: Dict[str, int] = {}

    for f in flags:
        sev = (f.severity or "medium").lower()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        field_counts[f.field_name] = field_counts.get(f.field_name, 0) + 1

    return {
        "total_flags": len(flags),
        "severity_breakdown": severity_counts,
        "frequent_discrepancy_fields": field_counts,
        "flags": [
            {
                "id": f.id,
                "session_id": f.pd_session_id,
                "field_name": f.field_name,
                "value_a": f.value_a,
                "value_b": f.value_b,
                "severity": f.severity,
                "resolution_note": f.resolution_note,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in flags
        ]
    }


@router.get("/analytics/case-funnel")
@router.get("/case-funnel")
@router.get("/cases")
def get_case_funnel_analytics(
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
) -> Dict[str, Any]:
    """
    Returns Application status funnel metrics across stages (Section 12).
    """
    total_cases = db.query(Application).count()
    status_counts: Dict[str, int] = {}

    for status_enum in ApplicationStatusEnum:
        c = db.query(Application).filter(Application.status == status_enum).count()
        status_counts[status_enum.value] = c

    conversion_rate = 0.0
    if total_cases > 0:
        completed = status_counts.get(ApplicationStatusEnum.PD_COMPLETE.value, 0) + status_counts.get(ApplicationStatusEnum.APPROVED.value, 0)
        conversion_rate = round((completed / total_cases) * 100.0, 2)

    return {
        "total_applications": total_cases,
        "funnel_stages": status_counts,
        "completion_rate_pct": conversion_rate
    }


@router.get("/analytics/proactive-bonus")
@router.get("/proactive-bonus")
@router.get("/leaderboard")
def get_proactive_bonus_leaderboard(
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
) -> Dict[str, Any]:
    """
    Leaderboard view of officer_proactive_bonus_points:
    A distinct positive underwriting signal surfaced on its own (Section 12).
    """
    officers = db.query(Officer).all()
    leaderboard = []

    for off in officers:
        scores = db.query(OfficerPDScore).filter(OfficerPDScore.officer_id == off.id).all()
        total_bonus = sum(s.proactive_diligence_bonus for s in scores)
        sessions_count = len(scores)

        leaderboard.append({
            "officer_id": off.id,
            "officer_name": off.name,
            "phone_number": off.phone_number,
            "total_proactive_bonus_points": total_bonus,
            "sessions_evaluated": sessions_count,
            "avg_bonus_per_session": round(total_bonus / max(1, sessions_count), 2)
        })

    # Sort descending by bonus points
    leaderboard.sort(key=lambda x: x["total_proactive_bonus_points"], reverse=True)

    return {
        "total_officers": len(leaderboard),
        "leaderboard": leaderboard
    }
