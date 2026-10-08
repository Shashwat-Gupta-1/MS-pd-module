"""Ground PD routes for Agent 3: Photo Upload, GPS/EXIF verification, Gemini Vision extraction,
and Application-level Asset Valuation summary.
"""
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agents.vision_extraction import aggregate_application_assets, extract_photo_vision
from app.core.config import settings
from app.core.database import get_db
from app.models.application import Application
from app.models.ground_pd_photo import GroundPDPhoto
from app.models.occupation_config import OccupationConfig
from app.models.photo_category_config import PhotoCategoryConfig
from app.models.photo_extraction import PhotoExtraction
from app.schemas.ground_pd_photo import PhotoResponse
from app.schemas.photo_extraction import ApplicationVisionSummary
from app.utils.completion_gate import check_photo_completion
from app.utils.gps_utils import (
    check_site_distance,
    extract_exif_metadata,
    verify_gps_accuracy,
    verify_live_capture,
)
from app.utils.image_hash import compute_phash, find_duplicate_photo

router = APIRouter(prefix="/ground-pd", tags=["Ground PD & Vision Agent"])


@router.post("/photos", response_model=Dict[str, Any])
async def upload_ground_pd_photo(
    file: UploadFile = File(...),
    application_id: str = Form(...),
    category: str = Form(...),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    accuracy_m: Optional[float] = Form(None),
    site_lat: Optional[float] = Form(None),
    site_lng: Optional[float] = Form(None),
    occupation_code: Optional[str] = Form("kirana"),
    db: Session = Depends(get_db),
):
    """Upload a site photo, perform live-camera EXIF & GPS validation,
    check for duplicate photos via perceptual hashing, and run Gemini Vision extraction.
    """
    # 1. Ensure target storage directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)

    # 2. Read uploaded file bytes
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 3. Generate unique photo ID and save file to local disk
    photo_id = f"photo_{uuid.uuid4().hex[:10]}"
    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    filename = f"{photo_id}{ext}"
    storage_path = os.path.join(settings.upload_dir, filename)

    with open(storage_path, "wb") as f:
        f.write(image_bytes)

    # 4. EXIF & Live Camera Verification
    exif_meta = extract_exif_metadata(image_bytes)
    is_live, captured_at, device_model, live_flags = verify_live_capture(exif_meta)

    # 5. GPS Accuracy & Site Distance Checks
    gps_status, acc_flags = verify_gps_accuracy(accuracy_m)
    dist_m, site_status, site_flags = check_site_distance(lat, lng, site_lat, site_lng)

    # 6. Perceptual Image Hashing & Duplicate Detection
    current_phash = compute_phash(image_bytes)
    all_stored_photos = db.query(GroundPDPhoto.id, GroundPDPhoto.application_id, GroundPDPhoto.phash).all()
    is_duplicate, dup_photo_id, dup_app_id, dup_flags = find_duplicate_photo(
        current_phash, all_stored_photos, application_id
    )

    # Combine all audit & risk flags
    combined_flags = list(set(live_flags + acc_flags + site_flags + dup_flags))

    # 7. Ensure Application record exists in DB
    app_obj = db.get(Application, application_id)
    if not app_obj:
        app_obj = Application(
            id=application_id,
            borrower_name="Ramesh Kumar",
            product_type="Micro Enterprise Loan",
            status="PD_IN_PROGRESS",
        )
        db.add(app_obj)
        db.flush()

    # 8. Save GroundPDPhoto model to PostgreSQL
    photo_obj = GroundPDPhoto(
        id=photo_id,
        application_id=application_id,
        category=category,
        file_name=filename,
        storage_path=storage_path,
        file_size_bytes=len(image_bytes),
        mime_type=file.content_type or "image/jpeg",
        lat=lat,
        lng=lng,
        accuracy_m=accuracy_m,
        gps_status=gps_status if gps_status != "VALID" else site_status,
        distance_to_site_m=dist_m,
        captured_at=captured_at,
        is_live_capture=is_live,
        device_model=device_model,
        phash=current_phash,
        is_duplicate=is_duplicate,
        duplicate_of_id=dup_photo_id,
        flags=combined_flags,
    )
    db.add(photo_obj)
    db.commit()

    # 9. Query DB dynamic prompt hints for the occupation and category
    category_rule = (
        db.query(PhotoCategoryConfig)
        .join(OccupationConfig)
        .filter(
            OccupationConfig.code == (occupation_code or "kirana").lower().strip(),
            PhotoCategoryConfig.category_code == category.lower().strip(),
        )
        .first()
    )

    occ_name = category_rule.occupation.name if category_rule else occupation_code
    cat_hints = category_rule.prompt_hints if category_rule else None
    val_guide = category_rule.valuation_guide if category_rule else None

    # 10. Run Gemini Vision Extraction
    extraction_dict = {}
    try:
        extraction_dict = extract_photo_vision(
            photo_path=storage_path,
            category=category,
            mime_type=file.content_type or "image/jpeg",
            occupation_name=occ_name,
            category_hints=cat_hints,
            valuation_guide=val_guide,
        )

        extraction_obj = PhotoExtraction(
            photo_id=photo_id,
            category_matches_photo=extraction_dict.get("category_matches_photo", True),
            category_mismatch_reason=extraction_dict.get("category_mismatch_reason"),
            premises_type=extraction_dict.get("premises_type"),
            stock_level=extraction_dict.get("stock_level"),
            employee_count_visible=int(extraction_dict.get("employee_count_visible", 0)),
            customer_activity_visible=extraction_dict.get("customer_activity_visible"),
            overall_condition=extraction_dict.get("overall_condition"),
            items=extraction_dict.get("items", []),
            estimated_total_value_min=extraction_dict.get("estimated_total_value_min", 0.0),
            estimated_total_value_max=extraction_dict.get("estimated_total_value_max", 0.0),
            summary=extraction_dict.get("summary"),
            raw_llm_json=extraction_dict,
        )
        db.add(extraction_obj)
        db.commit()

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Non-blocking: extraction failure can be retried without losing photo record
        extraction_dict = {"error": f"Vision extraction failed: {str(e)}"}

    # 11. Run application-level aggregation
    try:
        aggregate_application_assets(application_id, db)
    except Exception as agg_err:
        print(f"Aggregation warning: {agg_err}")

    return {
        "status": "success",
        "photo_id": photo_id,
        "application_id": application_id,
        "category": category,
        "file_name": filename,
        "photo_url": f"http://localhost:8000/uploads/photos/{filename}",
        "gps_status": photo_obj.gps_status,
        "distance_to_site_m": dist_m,
        "is_live_capture": is_live,
        "is_duplicate": is_duplicate,
        "flags": combined_flags,
        "extraction": extraction_dict,
    }


@router.get("/{application_id}/summary", response_model=Dict[str, Any])
def get_application_ground_pd_summary(
    application_id: str,
    occupation_code: Optional[str] = "kirana",
    db: Session = Depends(get_db),
):
    """Retrieve full Ground PD analysis summary for a loan application:
    all photos, audit flags, aggregated asset valuations, turnover estimates, and completion gate status.
    """
    photos = db.query(GroundPDPhoto).filter_by(application_id=application_id).all()

    # Aggregate physical assets
    agg_res = aggregate_application_assets(application_id, db)

    # Check mandatory category completion gate
    gate_res = check_photo_completion(application_id, occupation_code or "kirana", db)

    # Collect all audit flags across all photos
    all_flags = []
    photo_list = []
    for p in photos:
        if p.flags:
            all_flags.extend(p.flags)
        photo_list.append({
            "id": p.id,
            "category": p.category,
            "file_name": p.file_name,
            "gps_status": p.gps_status,
            "distance_to_site_m": p.distance_to_site_m,
            "is_live_capture": p.is_live_capture,
            "is_duplicate": p.is_duplicate,
            "flags": p.flags or [],
            "extraction": {
                "items": p.extraction.items if p.extraction else [],
                "premises_type": p.extraction.premises_type if p.extraction else None,
                "stock_level": p.extraction.stock_level if p.extraction else None,
                "overall_condition": p.extraction.overall_condition if p.extraction else None,
                "estimated_total_value_min": p.extraction.estimated_total_value_min if p.extraction else 0.0,
                "estimated_total_value_max": p.extraction.estimated_total_value_max if p.extraction else 0.0,
                "summary": p.extraction.summary if p.extraction else None,
            } if p.extraction else None,
        })

    return {
        "application_id": application_id,
        "total_photos": len(photos),
        "completion_gate": gate_res,
        "total_asset_value_min_inr": agg_res.get("total_asset_value_min_inr", 0.0),
        "total_asset_value_max_inr": agg_res.get("total_asset_value_max_inr", 0.0),
        "audit_flags": list(set(all_flags)),
        "aggregated_assets": agg_res.get("assets", []),
        "photos": photo_list,
    }


@router.delete("/{application_id}/photos", response_model=Dict[str, Any])
@router.post("/{application_id}/reset", response_model=Dict[str, Any])
def reset_application_photos(
    application_id: str,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Reset / delete photos for a specific category or wipe all categories for the loan application."""
    query = db.query(GroundPDPhoto).filter_by(application_id=application_id)
    if category:
        query = query.filter_by(category=category)

    photos_to_delete = query.all()
    deleted_count = len(photos_to_delete)

    for p in photos_to_delete:
        # Delete local file if exists
        try:
            if p.storage_path and os.path.exists(p.storage_path):
                os.remove(p.storage_path)
        except Exception:
            pass
        db.delete(p)

    db.commit()

    # Recalculate aggregated asset valuations
    try:
        aggregate_application_assets(application_id, db)
    except Exception as err:
        print(f"Post-reset aggregation warning: {err}")

    return {
        "status": "success",
        "application_id": application_id,
        "category_reset": category or "all",
        "deleted_count": deleted_count,
    }


@router.get("/occupations")
def get_occupations(db: Session = Depends(get_db)):
    """Retrieve all active occupations and their configured photo categories from PostgreSQL."""
    if db.query(OccupationConfig).count() == 0:
        seed_default_occupations(db)

    occupations = db.query(OccupationConfig).filter(OccupationConfig.is_active == True).all()
    result = []
    for occ in occupations:
        result.append({
            "id": occ.id,
            "code": occ.code,
            "name": occ.name,
            "description": occ.description,
            "categories": [
                {
                    "id": cat.id,
                    "category_code": cat.category_code,
                    "label": cat.label,
                    "min_photos": cat.min_photos,
                    "is_mandatory": cat.is_mandatory,
                    "prompt_hints": cat.prompt_hints,
                    "valuation_guide": cat.valuation_guide,
                }
                for cat in occ.categories
                if cat.is_active
            ],
        })
    return result


@router.post("/seed-config")
def seed_default_occupations(db: Session = Depends(get_db)):
    """Seed initial occupation types and mandatory photo category rules into PostgreSQL."""
    default_data = [
        {
            "code": "kirana",
            "name": "Kirana / Grocery Retail Store",
            "description": "General grocery and daily essentials retail shop",
            "categories": [
                {
                    "category_code": "shop_front",
                    "label": "Shop Front & Name Board",
                    "min_photos": 1,
                    "is_mandatory": True,
                    "prompt_hints": "Verify shop name signboard, entrance visibility, customer footfall access",
                    "valuation_guide": "Signboard and front setup typically INR 5,000 to 20,000",
                },
                {
                    "category_code": "shelf_inventory",
                    "label": "Stock & Shelf Inventory",
                    "min_photos": 2,
                    "is_mandatory": True,
                    "prompt_hints": "Identify FMCG stock density, packed provisions, shelf fullness percentage",
                    "valuation_guide": "Average Kirana shelf stock ranges from INR 50,000 to 5,00,000 based on density",
                },
                {
                    "category_code": "billing_counter",
                    "label": "Billing Counter & UPI QR",
                    "min_photos": 1,
                    "is_mandatory": True,
                    "prompt_hints": "Look for UPI QR codes (PhonePe, Paytm, GPay), cash drawer, electronic weighing scale",
                    "valuation_guide": "Counter and digital scale value INR 8,000 to 25,000",
                },
                {
                    "category_code": "storage_godown",
                    "label": "Backroom / Storage Godown",
                    "min_photos": 1,
                    "is_mandatory": False,
                    "prompt_hints": "Check bulk grain sacks, edible oil tins, beverage crates stored in reserve",
                    "valuation_guide": "Reserve inventory value INR 50,000 to 3,00,000",
                },
            ],
        },
        {
            "code": "dairy",
            "name": "Dairy Farming & Cattle",
            "description": "Smallholder dairy farming and livestock operations",
            "categories": [
                {
                    "category_code": "cattle_livestock",
                    "label": "Cattle & Livestock Herd",
                    "min_photos": 2,
                    "is_mandatory": True,
                    "prompt_hints": "Count milch cows/buffaloes, inspect health condition, ear tags if any",
                    "valuation_guide": "Milch buffalo value INR 60,000 to 90,000 each; Crossbred cow INR 40,000 to 70,000 each",
                },
                {
                    "category_code": "cattle_shed",
                    "label": "Cattle Shed & Feed Area",
                    "min_photos": 1,
                    "is_mandatory": True,
                    "prompt_hints": "Inspect tin shed structure, feeding mangers, water supply, cleanliness",
                    "valuation_guide": "Shed infrastructure value INR 30,000 to 1,50,000",
                },
                {
                    "category_code": "residence_collateral",
                    "label": "Residence / Collateral Property",
                    "min_photos": 1,
                    "is_mandatory": True,
                    "prompt_hints": "Inspect house structure (pucca/semi-pucca), boundary walls, approach road",
                    "valuation_guide": "Rural residential structure typically INR 3L to 15L",
                },
            ],
        },
        {
            "code": "garments",
            "name": "Garment & Tailoring Unit",
            "description": "Apparel stitching, boutique, and garment manufacturing",
            "categories": [
                {
                    "category_code": "sewing_machinery",
                    "label": "Sewing & Overlock Machines",
                    "min_photos": 1,
                    "is_mandatory": True,
                    "prompt_hints": "Count industrial sewing machines (Juki, Singer), motor attachments, overlock machines",
                    "valuation_guide": "Industrial sewing machine value INR 15,000 to 30,000 each",
                },
                {
                    "category_code": "fabric_stock",
                    "label": "Fabric Rolls & Finished Garments",
                    "min_photos": 1,
                    "is_mandatory": True,
                    "prompt_hints": "Estimate volume of fabric cloth rolls, cut pieces, finished dresses hanging",
                    "valuation_guide": "Cloth stock value INR 40,000 to 3,00,000",
                },
            ],
        },
    ]

    inserted_count = 0
    for occ_item in default_data:
        existing = db.query(OccupationConfig).filter_by(code=occ_item["code"]).first()
        if not existing:
            occ_obj = OccupationConfig(
                code=occ_item["code"],
                name=occ_item["name"],
                description=occ_item["description"],
            )
            db.add(occ_obj)
            db.flush()

            for cat_item in occ_item["categories"]:
                cat_obj = PhotoCategoryConfig(
                    occupation_id=occ_obj.id,
                    category_code=cat_item["category_code"],
                    label=cat_item["label"],
                    min_photos=cat_item["min_photos"],
                    is_mandatory=cat_item["is_mandatory"],
                    prompt_hints=cat_item["prompt_hints"],
                    valuation_guide=cat_item["valuation_guide"],
                )
                db.add(cat_obj)
            inserted_count += 1

    db.commit()
    return {"status": "success", "occupations_seeded": inserted_count}
