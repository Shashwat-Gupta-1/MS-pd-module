from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.applicant import Applicant
from app.models.pd_session import PDSession
from app.models.question_bank import QuestionBank
from app.models.extracted_field import ExtractedField
from app.models.gap_question import GapQuestion
from app.models.ground_pd_photo import GroundPDPhoto
from app.utils.gps_utils import check_cluster_tightness, get_cluster_max_distance


# Mandatory ground PD photo categories required for underwriting verification
MANDATORY_PHOTO_CATEGORIES = [
    "BUSINESS_EXTERIOR",
    "BUSINESS_INTERIOR",
    "MACHINERY_ASSETS",
    "OWNER_AT_PREMISES",
    "APPLICANT_PORTRAIT",
]

# Normalization map for common category aliases
CATEGORY_ALIASES = {
    "EXTERIOR": "BUSINESS_EXTERIOR",
    "BUSINESS_EXTERIOR": "BUSINESS_EXTERIOR",
    "INTERIOR": "BUSINESS_INTERIOR",
    "BUSINESS_INTERIOR": "BUSINESS_INTERIOR",
    "MACHINERY": "MACHINERY_ASSETS",
    "MACHINERY_ASSETS": "MACHINERY_ASSETS",
    "OWNER": "OWNER_AT_PREMISES",
    "OWNER_AT_PREMISES": "OWNER_AT_PREMISES",
    "APPLICANT": "APPLICANT_PORTRAIT",
    "APPLICANT_PORTRAIT": "APPLICANT_PORTRAIT",
}


def normalize_photo_category(cat: str) -> str:
    cleaned = (cat or "").strip().upper()
    return CATEGORY_ALIASES.get(cleaned, cleaned)


def check_completion(application_id: str, db: Session) -> Dict[str, Any]:
    """
    Hard-stop completion gate as specified in Section 9 of the Final Build Prompt:
    Returns {"complete": bool, "missing": list[str]}.
    Checks:
      1. Every mandatory QuestionBank field has an ExtractedField with status
         STATED or INFERRED (a mandatory field left NOT_CAPTURED triggers the manual-
         fallback UI flow, and blocks completion until filled).
      2. Every numeric field's needs_reconfirmation flag has been cleared by the officer
         (indicated by officer_confirmed=True).
      3. All 5 required GroundPDPhoto categories present (Exterior, Interior, Machinery,
         Owner, Applicant).
      4. GPS cluster tightness across those 5 photos' lat/lng <= 150m (reads straight off
         GroundPDPhoto rows populated during capture, zero maps API dependency).

    Does NOT check:
      - Unresolved gap_questions (status PENDING/DISMISSED only affect officer_pd_scores,
        never block completion).
      - Officer diligence score itself.
      - Customer consistency flag resolution status.
    The gate blocks strictly on missing hard data, never on quality/judgment signals.
    """
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        return {"complete": False, "missing": ["Application case not found"]}

    applicant = application.applicant
    if not applicant:
        return {"complete": False, "missing": ["Applicant profile not linked to application"]}

    missing: List[str] = []

    # 1. Fetch mandatory questions for Tier 1, Tier 2, Tier 3
    t1_mandatory = db.query(QuestionBank).filter(
        QuestionBank.tier == 1,
        QuestionBank.is_mandatory == True
    ).all()

    t2_mandatory = db.query(QuestionBank).filter(
        QuestionBank.tier == 2,
        QuestionBank.employment_type == applicant.employment_type,
        QuestionBank.is_mandatory == True
    ).all()

    tier3_query = db.query(QuestionBank).filter(
        QuestionBank.tier == 3,
        QuestionBank.is_mandatory == True
    )
    raw_cat = (applicant.business_category or applicant.employer_type or "").lower().replace(" ", "_")
    if raw_cat in ("govt", "government"):
        raw_cat = "salaried_govt"
    elif raw_cat in ("private", "corporate"):
        raw_cat = "salaried_private"

    if raw_cat:
        tier3_query = tier3_query.filter(
            QuestionBank.business_category == raw_cat
        )
    t3_mandatory = tier3_query.all()

    all_mandatory = t1_mandatory + t2_mandatory + t3_mandatory

    # Fetch latest session for this application
    latest_session = (
        db.query(PDSession)
        .filter(PDSession.application_id == application.id)
        .order_by(PDSession.started_at.desc())
        .first()
    )

    extracted_fields: List[ExtractedField] = []
    if latest_session:
        extracted_fields = (
            db.query(ExtractedField)
            .filter(ExtractedField.pd_session_id == latest_session.id)
            .all()
        )

    # Map extracted fields by lowercase field_name
    field_map: Dict[str, ExtractedField] = {
        ef.field_name.lower().strip(): ef for ef in extracted_fields
    }

    # Check each mandatory field has status STATED or INFERRED
    missing_mandatory_fields = []
    for q in all_mandatory:
        fname = q.field_name.lower().strip()
        ef = field_map.get(fname)
        if not ef:
            missing_mandatory_fields.append(f"Missing mandatory field: {q.field_name} ({q.question_text})")
        else:
            status = (ef.source or "").lower()
            val = str(ef.value or "").strip()
            # Must be STATED or INFERRED with actual non-empty value
            if status not in ("stated", "inferred") and not ef.officer_confirmed:
                missing_mandatory_fields.append(f"Mandatory field not captured: {q.field_name}")
            elif not val and not ef.officer_confirmed:
                missing_mandatory_fields.append(f"Mandatory field has empty value: {q.field_name}")

    if missing_mandatory_fields:
        missing.append(f"Mandatory questionnaire incomplete: {len(missing_mandatory_fields)} required fields missing.")
        missing.extend(missing_mandatory_fields)


    # 2. Check numeric fields reconfirmation
    for ef in extracted_fields:
        # If field represents numeric financial and requires confirmation
        is_numeric_metric = any(
            k in ef.field_name.lower()
            for k in ("turnover", "income", "sales", "margin", "emi", "obligation", "rent", "wage")
        )
        if is_numeric_metric and not ef.officer_confirmed and (ef.source or "").lower() != "stated":
            missing.append(f"Numeric field requires officer reconfirmation: {ef.field_name}")

    # 3. Check 5 required ground photo categories
    photos = db.query(GroundPDPhoto).filter(
        or_(
            GroundPDPhoto.application_id == application.id,
            GroundPDPhoto.pd_session_id == (latest_session.id if latest_session else None)
        )
    ).all()

    captured_categories = {normalize_photo_category(p.category) for p in photos if p.category}
    missing_photo_categories = []
    for req_cat in MANDATORY_PHOTO_CATEGORIES:
        if req_cat not in captured_categories:
            missing_photo_categories.append(req_cat)

    if missing_photo_categories:
        missing.append(f"Missing {len(missing_photo_categories)} mandatory photo categories: {', '.join(missing_photo_categories)}.")
        for mc in missing_photo_categories:
            missing.append(f"Missing required photo category: {mc}")


    # 4. Check GPS cluster tightness across photos (<= 150m)
    if photos and len(photos) > 1:
        if not check_cluster_tightness(photos, tolerance_m=150.0):
            max_d = get_cluster_max_distance(photos)
            missing.append(
                f"Photo GPS cluster exceeds 150m tolerance (maximum pairwise distance: {max_d:.1f}m)"
            )

    complete = len(missing) == 0
    return {
        "complete": complete,
        "missing": missing,
    }


class CompletionGateResult(BaseModel):
    is_complete: bool
    can_submit: bool
    completion_percentage: float
    blocking_reasons: List[str]
    warnings: List[str]
    details: Dict[str, Any]


def validate_session_completion(db: Session, session_id: str) -> CompletionGateResult:
    """Backward-compatible session completion validator."""
    session = db.query(PDSession).filter(PDSession.id == session_id).first()
    if not session:
        return CompletionGateResult(
            is_complete=False,
            can_submit=False,
            completion_percentage=0.0,
            blocking_reasons=["PD Session not found"],
            warnings=[],
            details={},
        )
    gate = check_completion(session.application_id, db)
    return CompletionGateResult(
        is_complete=gate["complete"],
        can_submit=gate["complete"],
        completion_percentage=100.0 if gate["complete"] else 50.0,
        blocking_reasons=gate["missing"],
        warnings=[],
        details=gate,
    )
