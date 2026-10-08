"""Completion Gate for Agent 3: Checks whether an application has fulfilled all mandatory
photo categories and required photo counts for its configured occupation.
"""
from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.models.ground_pd_photo import GroundPDPhoto
from app.models.occupation_config import OccupationConfig
from app.models.photo_category_config import PhotoCategoryConfig


def check_photo_completion(
    application_id: str,
    occupation_code: str,
    db: Session,
) -> Dict[str, Any]:
    """Evaluate photo completion against DB-configured occupation rules.
    Returns:
      {
         "is_complete": bool,
         "mandatory_total": int,
         "mandatory_fulfilled": int,
         "missing_categories": list[str],
         "category_breakdown": dict,
         "total_photos": int
      }
    """
    # 1. Fetch uploaded photos for this application
    photos = db.query(GroundPDPhoto).filter_by(application_id=application_id).all()
    uploaded_counts: Dict[str, int] = {}
    for p in photos:
        cat = p.category.lower().strip()
        uploaded_counts[cat] = uploaded_counts.get(cat, 0) + 1

    # 2. Fetch occupation configuration rules from DB
    occ_config = (
        db.query(OccupationConfig)
        .filter(OccupationConfig.code == occupation_code.lower().strip())
        .first()
    )

    if not occ_config:
        # Fallback to general rules if specific occupation not found
        occ_config = db.query(OccupationConfig).first()

    rules: List[PhotoCategoryConfig] = occ_config.categories if occ_config else []

    missing: List[str] = []
    category_breakdown: Dict[str, Any] = {}
    mandatory_total = 0
    mandatory_fulfilled = 0

    for rule in rules:
        if not rule.is_active:
            continue
        cat_key = rule.category_code.lower().strip()
        actual_count = uploaded_counts.get(cat_key, 0)
        req_count = rule.min_photos

        is_met = actual_count >= req_count
        category_breakdown[rule.label] = {
            "category_code": rule.category_code,
            "required": req_count,
            "uploaded": actual_count,
            "is_mandatory": rule.is_mandatory,
            "status": "COMPLETED" if is_met else "PENDING",
        }

        if rule.is_mandatory:
            mandatory_total += 1
            if is_met:
                mandatory_fulfilled += 1
            else:
                diff = req_count - actual_count
                missing.append(f"{rule.label} ({diff} more photo{'s' if diff > 1 else ''} required)")

    is_complete = (mandatory_total == mandatory_fulfilled) and (len(photos) > 0)

    return {
        "is_complete": is_complete,
        "total_photos": len(photos),
        "mandatory_total": mandatory_total,
        "mandatory_fulfilled": mandatory_fulfilled,
        "missing_categories": missing,
        "category_breakdown": category_breakdown,
        "occupation_name": occ_config.name if occ_config else occupation_code,
    }
