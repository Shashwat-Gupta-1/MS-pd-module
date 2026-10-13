from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_officer
from app.models.application import Application
from app.models.applicant import Applicant
from app.models.question_bank import QuestionBank
from app.models.officer import Officer
from app.schemas.question_bank import QuestionBankResponse
from app.services.questionnaire_loader import sync_questions_to_db

router = APIRouter()


@router.post("/reload", summary="Hot-reload questionnaire from JSON configuration files")
def reload_questions_from_files(
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    """Scan backend/app/data/questions/ and synchronize questions into the database."""
    stats = sync_questions_to_db(db)
    return {
        "status": "success",
        "message": "Questionnaire successfully synchronized from files",
        "details": stats
    }


@router.get("/categories", summary="Get dynamic employment types and tier-3 subcategories")
def get_questionnaire_categories(
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
) -> Dict[str, Any]:
    """Provides dynamically registered employment types and Tier 3 categories from question bank."""
    if db.query(QuestionBank).count() == 0:
        sync_questions_to_db(db)

    # Distinct categories for tier 3
    t3_items = db.query(QuestionBank.employment_type, QuestionBank.business_category).filter(
        QuestionBank.tier == 3,
        QuestionBank.business_category.isnot(None)
    ).distinct().all()

    self_employed_cats = []
    salaried_cats = []
    seen = set()

    for emp_type, cat in t3_items:
        if not cat or cat in seen:
            continue
        seen.add(cat)
        clean_name = cat.lower().replace(" ", "_")
        if emp_type == "self_employed" or clean_name in ("retail", "manufacturing", "services"):
            label = "Retail / Trading" if "retail" in clean_name else "Manufacturing / Job-Work" if "manufacturing" in clean_name else "Services / Repairs" if "services" in clean_name else clean_name.replace("_", " ").title()
            self_employed_cats.append({"id": clean_name, "label": label})
        elif emp_type == "salaried" or "salaried" in clean_name:
            label = "Government / PSU" if "govt" in clean_name else "Private Company / Corporate" if "private" in clean_name else clean_name.replace("_", " ").title()
            salaried_cats.append({"id": clean_name, "label": label})

    # Default fallbacks if empty
    if not self_employed_cats:
        self_employed_cats = [
            {"id": "retail", "label": "Retail / Trading"},
            {"id": "manufacturing", "label": "Manufacturing / Job-Work"},
            {"id": "services", "label": "Services / Repairs"}
        ]
    if not salaried_cats:
        salaried_cats = [
            {"id": "salaried_govt", "label": "Government / PSU"},
            {"id": "salaried_private", "label": "Private Company / Corporate"}
        ]

    return {
        "employment_types": [
            {
                "id": "self_employed",
                "label": "Self-Employed",
                "sub_category_field": "businessCategory",
                "sub_category_label": "Business Category",
                "categories": self_employed_cats
            },
            {
                "id": "salaried",
                "label": "Salaried",
                "sub_category_field": "employerType",
                "sub_category_label": "Employer Type",
                "categories": salaried_cats
            }
        ]
    }


@router.get("/tiers", summary="Get all Tier 1-3 questions across the master question bank")
def get_all_question_tiers(
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
) -> Dict[str, Any]:
    if db.query(QuestionBank).count() == 0:
        sync_questions_to_db(db)

    tier1 = db.query(QuestionBank).filter(QuestionBank.tier == 1).order_by(QuestionBank.id).all()
    tier2 = db.query(QuestionBank).filter(QuestionBank.tier == 2).order_by(QuestionBank.id).all()
    tier3 = db.query(QuestionBank).filter(QuestionBank.tier == 3).order_by(QuestionBank.id).all()

    return {
        "tier1_universal": [QuestionBankResponse.model_validate(q) for q in tier1],
        "tier2_branch": [QuestionBankResponse.model_validate(q) for q in tier2],
        "tier3_trade_specific": [QuestionBankResponse.model_validate(q) for q in tier3],
        "total_questions_count": len(tier1) + len(tier2) + len(tier3)
    }


@router.get("/{application_id}", summary="Get applicable Tier 1-3 questions for a loan case")
def get_case_questionnaire(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
) -> Dict[str, Any]:
    # Ensure database has questions loaded from files
    if db.query(QuestionBank).count() == 0:
        sync_questions_to_db(db)

    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    applicant: Applicant = application.applicant
    if not applicant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant profile not linked")

    # 1. Tier 1: Universal questions asked of every borrower
    tier1_qs = db.query(QuestionBank).filter(QuestionBank.tier == 1).order_by(QuestionBank.id).all()

    # 2. Tier 2: Branching based on employment_type (self_employed or salaried)
    emp_type = applicant.employment_type.lower() if applicant.employment_type else "self_employed"
    tier2_qs = db.query(QuestionBank).filter(
        QuestionBank.tier == 2,
        QuestionBank.employment_type == emp_type
    ).order_by(QuestionBank.id).all()

    # 3. Tier 3: Trade-specific baseline questions if category is identified
    tier3_query = db.query(QuestionBank).filter(QuestionBank.tier == 3)
    raw_cat = (applicant.business_category or applicant.employer_type or "").lower().replace(" ", "_")

    # Handle aliases like 'govt' -> 'salaried_govt', 'private' -> 'salaried_private'
    if raw_cat in ("govt", "government"):
        raw_cat = "salaried_govt"
    elif raw_cat in ("private", "corporate"):
        raw_cat = "salaried_private"

    if raw_cat:
        tier3_query = tier3_query.filter(
            QuestionBank.business_category == raw_cat
        )
    tier3_qs = tier3_query.order_by(QuestionBank.id).all()

    tier1_res = [QuestionBankResponse.model_validate(q) for q in tier1_qs]
    tier2_res = [QuestionBankResponse.model_validate(q) for q in tier2_qs]
    tier3_res = [QuestionBankResponse.model_validate(q) for q in tier3_qs]

    return {
        "application_id": application.id,
        "applicant_name": applicant.name,
        "employment_type": applicant.employment_type,
        "business_category": applicant.business_category or applicant.employer_type,
        "tier1_universal": tier1_res,
        "tier2_branch": tier2_res,
        "tier3_trade_specific": tier3_res,
        "total_questions_count": len(tier1_res) + len(tier2_res) + len(tier3_res),
    }
