import os
import pytest
from app.agents.report_narrative import generate_narrative_section
from app.agents.report_assembly import assemble_report
from app.models.applicant import Applicant, EmploymentTypeEnum
from app.models.application import Application, ApplicationStatusEnum
from app.models.officer import Officer
from app.models.pd_session import PDSession
from app.models.extracted_field import ExtractedField
from app.models.ground_pd_photo import GroundPDPhoto
from app.models.customer_consistency_flag import CustomerConsistencyFlag
from app.models.officer_pd_score import OfficerPDScore
from app.models.officer_remark import OfficerRemark


def test_generate_narrative_section():
    data = {
        "sub_profile": "RETAIL",
        "turnover": 250000,
        "margins": "12% net",
        "footfall": "Moderate steady daily customer traffic"
    }
    narrative = generate_narrative_section("business_overview", data)
    assert isinstance(narrative, str)
    assert len(narrative) > 20
    assert "[FLAGGED FOR MANUAL UNDERWRITER REVIEW" not in narrative


def test_assemble_report_end_to_end(db_session):
    officer = Officer(name="Field Officer", phone_number="9876543210", hashed_password="pw", role="OFFICER")
    db_session.add(officer)
    db_session.commit()

    applicant = Applicant(
        full_name="Rajesh Verma",
        phone_number="9876543219",
        pan_number="ABCDE1111F",
        employment_type=EmploymentTypeEnum.SELF_EMPLOYED,
        sub_profile="RETAIL"
    )
    db_session.add(applicant)
    db_session.commit()

    app = Application(
        case_number="APP-REPORT-001",
        applicant_id=applicant.id,
        loan_type="BUSINESS_LOAN",
        requested_amount=500000.0,
        status=ApplicationStatusEnum.PD_COMPLETE
    )
    db_session.add(app)
    db_session.commit()

    session = PDSession(
        application_id=app.id,
        officer_id=officer.id,
        channel="ground",
        status="complete",
        is_session_active=False
    )
    db_session.add(session)
    db_session.commit()

    # Add extracted field
    ef = ExtractedField(
        pd_session_id=session.id,
        field_name="monthly_turnover",
        value="300000",
        source="stated",
        officer_confirmed=True
    )
    db_session.add(ef)

    # Add photo
    photo = GroundPDPhoto(
        pd_session_id=session.id,
        photo_category="BUSINESS_EXTERIOR",
        file_path="/photos/exterior.jpg",
        gps_latitude=28.6139,
        gps_longitude=77.2090
    )
    db_session.add(photo)

    # Add remark
    remark = OfficerRemark(
        pd_session_id=session.id,
        remark_text="Stable retail shop in prime market locality."
    )
    db_session.add(remark)

    # Add score with proactive bonus
    score = OfficerPDScore(
        pd_session_id=session.id,
        officer_id=officer.id,
        coverage_score=95.0,
        suggestion_uptake_score=90.0,
        reconfirmation_diligence_score=100.0,
        proactive_diligence_bonus=4.0,
        overall_score=94.5
    )
    db_session.add(score)
    db_session.commit()

    report_path = assemble_report(str(app.id), db_session)
    assert report_path is not None
    assert os.path.exists(report_path)
    assert report_path.endswith(".pdf") or report_path.endswith(".html")

    # Read the report and verify that PII (PAN, phone) is masked!
    with open(report_path, "rb") as f:
        content = f.read()
    # "9876543219" should not be visible in raw plain text
    assert b"9876543219" not in content
