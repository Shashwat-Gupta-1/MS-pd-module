"""Agent 3: Vision + GPS Confirmation.
Sends photos to Gemini Vision with dynamically constructed prompts (Base prompt + Category prompt + DB Occupation hints).
Extracts detected assets, inventory levels, counts, conditions, and estimated INR valuation ranges.
Also aggregates physical assets across all photos for a loan application.
"""
import os
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
    }
