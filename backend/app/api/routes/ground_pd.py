import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.deps import get_db, get_current_officer
from app.models.officer import Officer
from app.models.ground_pd_photo import GroundPDPhoto
from app.models.asset_valuation import AssetValuation
from app.models.business_estimate import BusinessEstimate
from app.models.application import Application
from app.agents.vision_extraction import (
    process_and_save_photo_extraction,
    aggregate_application_assets,
    verify_photo_gps_cluster,
)
from app.workers.tasks import extract_photo_vision_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ground-pd", tags=["Ground PD & Vision Extraction"])


@router.post("/photos", summary="Upload Ground PD photo and run Vision extraction")
async def upload_ground_pd_photo(
    application_id: Optional[str] = Form(None),
    pd_session_id: Optional[str] = Form(None),
    category: str = Form(...),
    lat: float = Form(26.9124),
    lng: float = Form(75.7873),
    accuracy_radius: Optional[float] = Form(10.0),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer),
):
    """
    Receives photo + GPS metadata, writes image to disk, and runs Agent 3 vision extraction.
    """
    file_url = f"/media/photos/photo_{category.lower()}.jpg"
    if file:
        photo_dir = settings.PHOTO_DIR
        photo_dir.mkdir(parents=True, exist_ok=True)
        unique_prefix = f"{application_id or pd_session_id or 'visit'}_{int(datetime.now(timezone.utc).timestamp())}"
        disk_path = photo_dir / f"{unique_prefix}_{file.filename}"
        content = await file.read()
        with open(disk_path, "wb") as f:
            f.write(content)
        file_url = f"/media/photos/{disk_path.name}"

    photo = GroundPDPhoto(
        application_id=application_id,
        pd_session_id=pd_session_id,
        category=category,
        url=file_url,
        lat=lat,
        lng=lng,
        accuracy_radius=accuracy_radius or 10.0,
        captured_at=datetime.now(timezone.utc),
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)

    extraction_res = None
    if file:
        try:
            extraction_res = process_and_save_photo_extraction(photo.id, db)
        except Exception as e:
            logger.warning(f"Vision extraction failed for photo {photo.id}: {e}")

    return {
        "status": "success",
        "photo_id": photo.id,
        "application_id": photo.application_id,
        "category": photo.category,
        "url": photo.url,
        "lat": photo.lat,
        "lng": photo.lng,
        "captured_at": photo.captured_at.isoformat(),
        "extraction": extraction_res.get("extraction") if extraction_res else None,
    }


@router.post("/photos/{photo_id}/extract", summary="Run or rerun Vision extraction for a photo")
def extract_single_photo(
    photo_id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer),
):
    """Manually triggers Agent 3 vision extraction on an existing photo."""
    photo = db.query(GroundPDPhoto).filter_by(id=photo_id).first()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    try:
        res = process_and_save_photo_extraction(photo_id, db)
        return {"status": "success", "result": res}
    except Exception as e:
        logger.error(f"Vision extraction error on photo {photo_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vision extraction error: {str(e)}",
        )


@router.post("/photos/{photo_id}/extract-async", summary="Dispatch background Celery Vision extraction for a photo")
def extract_single_photo_async(
    photo_id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer),
):
    """
    Dispatches Agent 3 extraction to Celery worker in the background.
    Safely falls back to synchronous execution if Celery broker is unavailable.
    """
    photo = db.query(GroundPDPhoto).filter_by(id=photo_id).first()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    try:
        task = extract_photo_vision_task.delay(photo_id)
        return {
            "status": "queued",
            "task_id": task.id,
            "photo_id": photo_id,
            "message": "Vision extraction dispatched to Celery worker."
        }
    except Exception as e:
        logger.warning(f"Celery dispatch failed for photo {photo_id}: {e}. Executing synchronously as fallback.")
        try:
            res = process_and_save_photo_extraction(photo_id, db)
            return {
                "status": "completed_fallback_sync",
                "photo_id": photo_id,
                "result": res
            }
        except Exception as sync_err:
            logger.error(f"Synchronous fallback failed for photo {photo_id}: {sync_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vision extraction error: {str(sync_err)}"
            )


@router.get("/applications/{application_id}/assets", summary="Get aggregated physical assets and business estimate")
def get_application_assets(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer),
):
    """Returns all aggregated physical assets and the overall business estimate."""
    app = db.query(Application).filter_by(id=application_id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    assets = db.query(AssetValuation).filter_by(application_id=application_id).all()
    b_est = db.query(BusinessEstimate).filter_by(application_id=application_id).first()
    gps_status = verify_photo_gps_cluster(application_id, db)

    return {
        "application_id": application_id,
        "asset_count": len(assets),
        "assets": [
            {
                "id": a.id,
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
            for a in assets
        ],
        "business_estimate": {
            "estimated_stock_value": b_est.estimated_stock_value if b_est else 0.0,
            "estimated_machinery_value": b_est.estimated_machinery_value if b_est else 0.0,
            "total_physical_assets_min": b_est.total_physical_assets_min if b_est else 0.0,
            "total_physical_assets_max": b_est.total_physical_assets_max if b_est else 0.0,
            "activity_level": b_est.activity_level if b_est else "medium",
            "consistency_with_declared_income": b_est.consistency_with_declared_income if b_est else "MATCH",
            "justification": b_est.justification if b_est else None,
        } if b_est else None,
        "gps_cluster": gps_status,
    }


@router.post("/applications/{application_id}/aggregate", summary="Re-aggregate physical assets across all photos")
def run_aggregation(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer),
):
    """Recomputes physical asset totals and updates BusinessEstimate for an application."""
    app = db.query(Application).filter_by(id=application_id).first()
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    res = aggregate_application_assets(application_id, db)
    return {"status": "success", "result": res}


@router.get("/applications/{application_id}/gps-verify", summary="Verify photo GPS cluster tightness")
def verify_gps(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer),
):
    """Verifies that all photos taken for this application satisfy GPS tightness (<=150m)."""
    return verify_photo_gps_cluster(application_id, db)
