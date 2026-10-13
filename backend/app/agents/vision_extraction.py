"""Agent 3: Vision + GPS Confirmation.
Sends photos to Gemini Vision with dynamically constructed prompts (Base prompt + Category prompt + DB Occupation hints).
Extracts detected assets, inventory levels, counts, conditions, and estimated INR valuation ranges.
Also aggregates physical assets across all photos for a loan application.
"""
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.agents.llm_client import get_llm
from app.core.config import settings
from app.models.asset_valuation import AssetValuation
from app.models.business_estimate import BusinessEstimate
from app.models.ground_pd_photo import GroundPDPhoto
from app.models.occupation_config import OccupationConfig
from app.models.photo_category_config import PhotoCategoryConfig
from app.models.photo_extraction import PhotoExtraction
from app.models.application import Application
from app.models.applicant import Applicant
from app.utils.gps_utils import (
    haversine_distance,
    verify_gps_accuracy,
    check_site_distance,
    extract_exif_metadata,
    verify_live_capture,
    check_cluster_tightness,
    get_cluster_max_distance,
)
from app.utils.image_hash import compute_phash, find_duplicate_photo

logger = logging.getLogger(__name__)


BASE_VISION_SYSTEM_PROMPT = """You are an expert Credit PD (Personal Discussion) Vision & Asset Valuation Auditor for an Indian MSME lending institution (MS Fincap).
Your job is to analyze photos taken at a borrower's business premises or collateral property.

Extract exact visual facts:
1. Item Detection: Identify all physical machinery, equipment, stock/inventory items, cattle/livestock, vehicles, or property assets present.
2. Count & Condition: Note the count and condition (new, good, fair, poor) of each item.
3. Valuation Range (in INR): Provide realistic market valuation range (min & max in Indian Rupees - INR) per unit and in total for identified items, typical for Indian local business context.
4. Premises Assessment: Identify premises type (e.g., retail_shop, workshop, godown, cattle_shed, residence), stock fill level (empty, low, medium, high, overstocked), and visible employee count.
5. Category Consistency: Verify whether the photo content matches the intended uploaded category.

You must respond ONLY in valid JSON matching this schema:
{
  "category_matches_photo": true,
  "category_mismatch_reason": null,
  "premises_type": "retail_shop",
  "stock_level": "medium",
  "employee_count_visible": 1,
  "customer_activity_visible": "low",
  "overall_condition": "good",
  "items": [
    {
      "name": "Display Glass Counter",
      "count": 2,
      "condition": "good",
      "unit_value_min_inr": 8000,
      "unit_value_max_inr": 12000,
      "total_value_min_inr": 16000,
      "total_value_max_inr": 24000
    }
  ],
  "estimated_total_value_min": 16000,
  "estimated_total_value_max": 24000,
  "summary": "Brief 1-2 sentence description of what is seen in the photo."
}
"""


def extract_photo_vision(
    photo_path: str,
    category: str,
    mime_type: str = "image/jpeg",
    occupation_name: Optional[str] = None,
    category_hints: Optional[str] = None,
    valuation_guide: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute Gemini Vision extraction on a single photo file."""
    if not os.path.exists(photo_path):
        raise FileNotFoundError(f"Photo not found on disk: {photo_path}")

    with open(photo_path, "rb") as f:
        image_bytes = f.read()

    # Build dynamic prompt
    user_prompt_lines = [
        f"Uploaded Category: {category}",
    ]
    if occupation_name:
        user_prompt_lines.append(f"Borrower Occupation: {occupation_name}")
    if category_hints:
        user_prompt_lines.append(f"Special Verification Hints: {category_hints}")
    if valuation_guide:
        user_prompt_lines.append(f"Valuation Reference Guide: {valuation_guide}")

    user_prompt_lines.append(
        "\nPlease inspect the attached image carefully and provide the structured JSON asset and premises analysis."
    )
    user_prompt = "\n".join(user_prompt_lines)

    llm = get_llm(model=settings.vision_model)
    result = llm.complete_json(
        system=BASE_VISION_SYSTEM_PROMPT,
        user=user_prompt,
        image_bytes=image_bytes,
        mime_type=mime_type,
    )

    # Sanitize and ensure numeric fields
    items = result.get("items", [])
    for it in items:
        count = int(it.get("count", 1))
        it["count"] = max(count, 1)
        it["unit_value_min_inr"] = float(it.get("unit_value_min_inr", 0.0))
        it["unit_value_max_inr"] = float(it.get("unit_value_max_inr", 0.0))
        if "total_value_min_inr" not in it or it["total_value_min_inr"] == 0:
            it["total_value_min_inr"] = it["unit_value_min_inr"] * it["count"]
        if "total_value_max_inr" not in it or it["total_value_max_inr"] == 0:
            it["total_value_max_inr"] = it["unit_value_max_inr"] * it["count"]

    if "estimated_total_value_min" not in result:
        result["estimated_total_value_min"] = sum(it["total_value_min_inr"] for it in items)
    if "estimated_total_value_max" not in result:
        result["estimated_total_value_max"] = sum(it["total_value_max_inr"] for it in items)

    return result


def aggregate_application_assets(application_id: str, db: Session) -> Dict[str, Any]:
    """Aggregate physical items and valuation across all photos for this loan application."""
    photos = (
        db.query(GroundPDPhoto)
        .filter_by(application_id=application_id)
        .all()
    )

    db.query(AssetValuation).filter_by(application_id=application_id).delete()

    aggregated_items: Dict[str, Dict[str, Any]] = {}
    total_val_min = 0.0
    total_val_max = 0.0
    stock_val_sum = 0.0
    machinery_val_sum = 0.0

    for p in photos:
        if not p.extraction or not p.extraction.items:
            continue
        for item in p.extraction.items:
            name = item.get("name", "Unknown Asset").strip().title()
            count = int(item.get("count", 1))
            cond = item.get("condition", "good")
            u_min = float(item.get("unit_value_min_inr", 0.0))
            u_max = float(item.get("unit_value_max_inr", 0.0))
            t_min = float(item.get("total_value_min_inr", u_min * count))
            t_max = float(item.get("total_value_max_inr", u_max * count))

            key = f"{p.category}_{name}"
            if key not in aggregated_items:
                aggregated_items[key] = {
                    "category": p.category,
                    "item_name": name,
                    "total_count": count,
                    "condition": cond,
                    "unit_value_min_inr": u_min,
                    "unit_value_max_inr": u_max,
                    "total_value_min_inr": t_min,
                    "total_value_max_inr": t_max,
                    "source_photo_ids": [p.id],
                }
            else:
                aggregated_items[key]["total_count"] += count
                aggregated_items[key]["total_value_min_inr"] += t_min
                aggregated_items[key]["total_value_max_inr"] += t_max
                if p.id not in aggregated_items[key]["source_photo_ids"]:
                    aggregated_items[key]["source_photo_ids"].append(p.id)

            total_val_min += t_min
            total_val_max += t_max

            if "stock" in p.category.lower() or "shelf" in p.category.lower() or "inventory" in p.category.lower():
                stock_val_sum += (t_min + t_max) / 2.0
            else:
                machinery_val_sum += (t_min + t_max) / 2.0

    # Persist aggregated asset valuations
    saved_assets = []
    for data in aggregated_items.values():
        av = AssetValuation(
            application_id=application_id,
            category=data["category"],
            item_name=data["item_name"],
            total_count=data["total_count"],
            condition=data["condition"],
            unit_value_min_inr=data["unit_value_min_inr"],
            unit_value_max_inr=data["unit_value_max_inr"],
            total_value_min_inr=data["total_value_min_inr"],
            total_value_max_inr=data["total_value_max_inr"],
            source_photo_ids=data["source_photo_ids"],
        )
        db.add(av)
        saved_assets.append(av)

    # Upsert BusinessEstimate
    b_est = db.query(BusinessEstimate).filter_by(application_id=application_id).first()
    if not b_est:
        b_est = BusinessEstimate(application_id=application_id)
        db.add(b_est)

    b_est.estimated_stock_value = stock_val_sum
    b_est.estimated_machinery_value = machinery_val_sum
    b_est.total_physical_assets_min = total_val_min
    b_est.total_physical_assets_max = total_val_max
    b_est.activity_level = "medium"
    b_est.consistency_with_declared_income = "MATCH"
    b_est.justification = f"Derived from {len(photos)} site photos. Total physical assets valued at INR {round(total_val_min):,} - {round(total_val_max):,}."

    db.commit()

    return {
        "assets": [
            {
                "category": a.category,
                "item_name": a.item_name,
                "total_count": a.total_count,
                "condition": a.condition,
                "unit_value_min_inr": a.unit_value_min_inr,
                "unit_value_max_inr": a.unit_value_max_inr,
                "total_value_min_inr": a.total_value_min_inr,
                "total_value_max_inr": a.total_value_max_inr,
                "source_photo_ids": a.source_photo_ids or [],
            }
            for a in saved_assets
        ],
        "total_asset_value_min_inr": total_val_min,
        "total_asset_value_max_inr": total_val_max,
        "estimated_stock_value": stock_val_sum,
        "estimated_machinery_value": machinery_val_sum,
    }


def resolve_photo_disk_path(photo_url: str) -> Optional[str]:
    """Helper to locate a photo file on disk from its stored URL or path."""
    if not photo_url:
        return None

    # Check direct path
    candidate = Path(photo_url)
    if candidate.exists() and candidate.is_file():
        return str(candidate.resolve())

    # Check relative to uploads / PHOTO_DIR
    fname = Path(photo_url).name
    candidates = [
        settings.PHOTO_DIR / fname,
        settings.PHOTOS_DIR / fname,
        settings.UPLOAD_DIR / "photos" / fname,
        settings.UPLOAD_DIR / fname,
        Path("uploads") / "photos" / fname,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return str(c.resolve())

    return None


def process_and_save_photo_extraction(photo_id: str, db: Session) -> Dict[str, Any]:
    """
    High-level agent runner for a single GroundPDPhoto:
    1. Finds photo record in DB.
    2. Resolves file on disk.
    3. Looks up Occupation and Category hints.
    4. Runs extract_photo_vision.
    5. Persists PhotoExtraction.
    6. Re-aggregates application assets across all photos.
    """
    photo = db.query(GroundPDPhoto).filter_by(id=photo_id).first()
    if not photo:
        raise ValueError(f"GroundPDPhoto not found: {photo_id}")

    disk_path = resolve_photo_disk_path(photo.url)
    if not disk_path:
        raise FileNotFoundError(f"Photo file could not be found on disk for URL: {photo.url}")

    with open(disk_path, "rb") as f:
        img_bytes = f.read()

    # 1. EXIF metadata & live capture check
    exif_meta = extract_exif_metadata(img_bytes)
    is_live, exif_captured_at, dev_model, exif_flags = verify_live_capture(exif_meta)

    # 2. Perceptual Hash (pHash) & duplicate detection against prior photos
    phash_str = compute_phash(img_bytes)
    stored_photos = [
        (p.id, p.application_id or "", p.phash)
        for p in db.query(GroundPDPhoto).filter(GroundPDPhoto.id != photo.id, GroundPDPhoto.phash.isnot(None)).all()
    ]
    is_dup, dup_photo_id, dup_app_id, dup_flags = find_duplicate_photo(
        phash_str, stored_photos, photo.application_id or ""
    )

    # 3. GPS accuracy radius check
    gps_status, gps_flags = verify_gps_accuracy(photo.accuracy_radius)

    # Consolidate audit flags onto photo record
    existing_flags = list(photo.flags or [])
    for fl in (exif_flags + dup_flags + gps_flags):
        if fl not in existing_flags:
            existing_flags.append(fl)

    if phash_str:
        photo.phash = phash_str
    if dev_model:
        photo.device_model = dev_model
    if exif_captured_at:
        photo.exif_captured_at = exif_captured_at
    photo.is_live_capture = is_live
    photo.gps_accuracy_status = gps_status
    photo.flags = existing_flags

    # Resolve applicant occupation
    occupation_name: Optional[str] = None
    if photo.application_id:
        app = db.query(Application).filter_by(id=photo.application_id).first()
        if app and app.applicant_id:
            applicant = db.query(Applicant).filter_by(id=app.applicant_id).first()
            if applicant:
                occupation_name = applicant.sub_profile or applicant.business_category

    # DB occupation config hints
    category_hints: Optional[str] = None
    valuation_guide: Optional[str] = None
    if occupation_name:
        occ_cfg = db.query(OccupationConfig).filter_by(occupation_name=occupation_name).first()
        if occ_cfg:
            category_hints = occ_cfg.category_hints
            valuation_guide = occ_cfg.valuation_guide

    # Category config
    cat_cfg = db.query(PhotoCategoryConfig).filter_by(category_name=photo.category).first()
    if cat_cfg:
        if cat_cfg.category_hints:
            category_hints = f"{category_hints or ''} | {cat_cfg.category_hints}".strip(" |")
        if cat_cfg.valuation_guide:
            valuation_guide = f"{valuation_guide or ''} | {cat_cfg.valuation_guide}".strip(" |")

    # Determine mime-type
    mime_type = "image/jpeg"
    lower_path = disk_path.lower()
    if lower_path.endswith(".png"):
        mime_type = "image/png"
    elif lower_path.endswith(".webp"):
        mime_type = "image/webp"

    # Execute vision extraction
    raw_res = extract_photo_vision(
        photo_path=disk_path,
        category=photo.category,
        mime_type=mime_type,
        occupation_name=occupation_name,
        category_hints=category_hints,
        valuation_guide=valuation_guide,
    )

    # Upsert PhotoExtraction
    pe = db.query(PhotoExtraction).filter_by(photo_id=photo.id).first()
    if not pe:
        pe = PhotoExtraction(photo_id=photo.id)
        db.add(pe)

    pe.category_matches_photo = raw_res.get("category_matches_photo", True)
    pe.category_mismatch_reason = raw_res.get("category_mismatch_reason")
    pe.premises_type = raw_res.get("premises_type")
    pe.stock_level = raw_res.get("stock_level")
    pe.employee_count_visible = int(raw_res.get("employee_count_visible", 0))
    pe.customer_activity_visible = raw_res.get("customer_activity_visible")
    pe.overall_condition = raw_res.get("overall_condition")
    pe.items = raw_res.get("items", [])
    pe.estimated_total_value_min = float(raw_res.get("estimated_total_value_min", 0.0))
    pe.estimated_total_value_max = float(raw_res.get("estimated_total_value_max", 0.0))
    pe.summary = raw_res.get("summary")
    pe.raw_extraction = raw_res

    # Legacy fields
    if pe.items:
        first_item = pe.items[0]
        pe.machinery_type = first_item.get("name")
        pe.approx_count = first_item.get("count", 1)
        pe.condition = first_item.get("condition", "good")

    db.commit()
    db.refresh(pe)

    # Aggregate across application
    if photo.application_id:
        try:
            aggregate_application_assets(photo.application_id, db)
        except Exception as agg_err:
            logger.warning(f"Error aggregating application assets after photo extraction: {agg_err}")

    return {
        "photo_id": photo.id,
        "category": photo.category,
        "extraction": raw_res,
    }


def verify_photo_gps_cluster(application_id: str, db: Session, tolerance_m: float = 150.0) -> Dict[str, Any]:
    """Runs GPS cluster tightness verification across all visit photos for an application."""
    photos = db.query(GroundPDPhoto).filter_by(application_id=application_id).all()
    if not photos or len(photos) <= 1:
        return {
            "within_tolerance": True,
            "photo_count": len(photos),
            "max_distance_meters": 0.0,
            "status": "PASS" if photos else "NO_PHOTOS",
        }

    is_tight = check_cluster_tightness(photos, tolerance_m=tolerance_m)
    max_dist = get_cluster_max_distance(photos)

    return {
        "within_tolerance": is_tight,
        "photo_count": len(photos),
        "max_distance_meters": round(max_dist, 2),
        "tolerance_meters": tolerance_m,
        "status": "PASS" if is_tight else "FAIL",
    }
