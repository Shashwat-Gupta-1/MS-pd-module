import logging
from typing import Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models.pd_session import PDSession
from app.models.officer_pd_score import OfficerPDScore
from app.models.extracted_field import ExtractedField
from app.models.gap_question import GapQuestion
from app.models.ground_pd_photo import GroundPDPhoto
from app.models.question_bank import QuestionBank
from app.utils.completion_gate import normalize_photo_category, MANDATORY_PHOTO_CATEGORIES

logger = logging.getLogger(__name__)

# Configurable score weights
WEIGHT_COVERAGE = 0.40
WEIGHT_UPTAKE = 0.35
WEIGHT_PHOTO = 0.25


def compute_officer_pd_score(
    session_id: str,
    db: Session,
    weight_coverage: float = WEIGHT_COVERAGE,
    weight_uptake: float = WEIGHT_UPTAKE,
    weight_photo: float = WEIGHT_PHOTO
) -> OfficerPDScore:
    """
    Computes objective officer diligence scores at end-of-session (Section 7):
    - questionnaire_coverage_score: % of mandatory baseline fields with status STATED or INFERRED
    - followup_uptake_score: % of AI-suggested follow-ups asked by officer (100 if none generated)
    - photo_diligence_score: % of 5 required photo categories captured
    - proactive_diligence_bonus: unprompted relevant underwriting questions (KEPT SEPARATE)
    - overall_score: weighted composite of the first three
    """
    session = db.query(PDSession).filter(PDSession.id == session_id).first()
    if not session:
        raise ValueError(f"PDSession {session_id} not found")

    officer_id = session.officer_id
    app = session.application
    applicant = app.applicant if app else None

    # 1. Questionnaire Coverage Score
    # Find all mandatory questions applicable to this application
    mandatory_questions = []
    if applicant:
        emp_val = applicant.employment_type
        emp_type = emp_val.value if hasattr(emp_val, "value") else str(emp_val or "SELF_EMPLOYED")
        sub_val = applicant.sub_profile
        sub_prof = (sub_val.value if hasattr(sub_val, "value") else str(sub_val or "RETAIL")).upper()

        # Tier 1 universal mandatory
        t1 = db.query(QuestionBank).filter(
            QuestionBank.tier == 1,
            QuestionBank.is_mandatory == True
        ).all()
        # Tier 2 mandatory
        t2 = db.query(QuestionBank).filter(
            QuestionBank.tier == 2,
            or_(
                QuestionBank.employment_type == emp_type,
                QuestionBank.employment_type == emp_type.lower()
            ),
            QuestionBank.is_mandatory == True
        ).all()
        # Tier 3 mandatory
        t3 = db.query(QuestionBank).filter(
            QuestionBank.tier == 3,
            or_(
                QuestionBank.business_category == sub_prof,
                QuestionBank.business_category == sub_prof.lower()
            ),
            QuestionBank.is_mandatory == True
        ).all()
        mandatory_questions = t1 + t2 + t3

    total_mandatory = len(mandatory_questions)
    captured_mandatory = 0

    if total_mandatory > 0:
        extracted = db.query(ExtractedField).filter(
            ExtractedField.pd_session_id == session_id
        ).all()
        captured_field_names = {
            ef.field_name.lower(): ef.source.lower()
            for ef in extracted
            if ef.source and ef.source.lower() in ("stated", "inferred")
        }
        for q in mandatory_questions:
            q_code = (getattr(q, "question_code", None) or getattr(q, "field_name", None) or "").lower()
            q_field = (getattr(q, "field_name", None) or q_code or "").lower()
            if (q_code and q_code in captured_field_names) or (q_field and q_field in captured_field_names):
                captured_mandatory += 1

        coverage_score = round((captured_mandatory / total_mandatory) * 100.0, 2)
    else:
        # Fallback if question bank is unseeded: check all extracted fields in session
        total_ef = db.query(ExtractedField).filter(ExtractedField.pd_session_id == session_id).count()
        valid_ef = db.query(ExtractedField).filter(
            ExtractedField.pd_session_id == session_id,
            ExtractedField.source.in_(["stated", "inferred", "STATED", "INFERRED"])
        ).count()
        coverage_score = round((valid_ef / max(1, total_ef)) * 100.0, 2) if total_ef > 0 else 100.0

    # 2. Follow-up Uptake Score
    total_gaps = db.query(GapQuestion).filter(GapQuestion.pd_session_id == session_id).count()
    if total_gaps == 0:
        # Do not penalize an officer whose discussion was thorough enough that no gaps appeared
        uptake_score = 100.0
    else:
        resolved_gaps = db.query(GapQuestion).filter(
            GapQuestion.pd_session_id == session_id,
            GapQuestion.resolved == True
        ).count()
        uptake_score = round((resolved_gaps / total_gaps) * 100.0, 2)

    # 3. Photo Diligence Score
    photos = db.query(GroundPDPhoto).filter(
        or_(
            GroundPDPhoto.pd_session_id == session_id,
            GroundPDPhoto.application_id == (app.id if app else None)
        )
    ).all()
    present_categories = {normalize_photo_category(p.category) for p in photos if p.category}
    required_categories = set(MANDATORY_PHOTO_CATEGORIES)
    matched_cats = present_categories.intersection(required_categories)
    photo_score = round((len(matched_cats) / len(required_categories)) * 100.0, 2)

    # 4. Proactive Diligence Bonus (Kept separate!)
    existing_score = db.query(OfficerPDScore).filter(OfficerPDScore.pd_session_id == session_id).first()
    bonus_points = existing_score.proactive_diligence_bonus if existing_score else 0.0

    # 5. Overall Score (Weighted combination of coverage, uptake, and photo diligence)
    overall_score = round(
        (weight_coverage * coverage_score) +
        (weight_uptake * uptake_score) +
        (weight_photo * photo_score),
        2
    )

    if existing_score:
        existing_score.coverage_score = coverage_score
        existing_score.suggestion_uptake_score = uptake_score
        existing_score.reconfirmation_diligence_score = photo_score
        existing_score.overall_score = overall_score
        existing_score.proactive_diligence_bonus = bonus_points
        score_obj = existing_score
    else:
        score_obj = OfficerPDScore(
            pd_session_id=session_id,
            officer_id=officer_id,
            coverage_score=coverage_score,
            suggestion_uptake_score=uptake_score,
            reconfirmation_diligence_score=photo_score,
            proactive_diligence_bonus=bonus_points,
            overall_score=overall_score
        )
        db.add(score_obj)

    db.commit()
    logger.info(
        f"Computed Officer PD Score for session {session_id}: "
        f"Coverage={coverage_score}%, Uptake={uptake_score}%, Photo={photo_score}%, "
        f"Bonus={bonus_points} pts, Overall={overall_score}/100"
    )
    return score_obj
