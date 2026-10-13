from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_officer
from app.core.config import settings
from app.models.application import Application
from app.models.officer import Officer
from app.agents.report_assembly import assemble_report, compile_cam_data

router = APIRouter()


@router.get("/{application_id}/data", summary="Get compiled Credit Assessment Memorandum (CAM) JSON data")
def get_cam_report_data(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {application_id} not found"
        )
    try:
        data = compile_cam_data(application_id, db)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compile CAM report data: {str(e)}"
        )


@router.get("/{application_id}", summary="Download compiled Credit Assessment Memorandum (CAM) PDF")
def download_cam_report(
    application_id: str,
    db: Session = Depends(get_db),
    current_officer: Officer = Depends(get_current_officer)
):
    application = db.query(Application).filter(Application.id == application_id).first()
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {application_id} not found"
        )

    # Check for existing report in reports upload directory
    report_filename = f"cam_report_{application_id}.pdf"
    reports_dir = getattr(settings, "REPORTS_DIR", getattr(settings, "REPORT_DIR", Path("uploads/reports")))
    report_path = Path(reports_dir) / report_filename

    if not report_path.exists():
        # Attempt to assemble on-the-fly if not already generated
        try:
            generated_path = assemble_report(application_id, db)
            report_path = Path(generated_path)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CAM report could not be generated: {str(e)}"
            )

    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CAM report file not found on disk"
        )

    return FileResponse(
        path=str(report_path),
        media_type="application/pdf",
        filename=f"MSFincap_CAM_{application_id}.pdf"
    )
