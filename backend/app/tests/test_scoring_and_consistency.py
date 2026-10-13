import pytest
from app.models.officer import Officer
from app.models.applicant import Applicant, EmploymentTypeEnum
from app.models.application import Application, ApplicationStatusEnum
from app.models.pd_session import PDSession
from app.models.extracted_field import ExtractedField
from app.models.gap_question import GapQuestion
from app.models.ground_pd_photo import GroundPDPhoto
from app.models.customer_consistency_flag import CustomerConsistencyFlag
from app.models.officer_pd_score import OfficerPDScore
from app.agents.officer_scoring import compute_officer_pd_score
from app.agents.customer_consistency import finalize_consistency_flags


@pytest.fixture
def scoring_setup(db_session):
    officer = Officer(name="Field Officer", phone_number="9876543210", hashed_password="pw", role="OFFICER")
    db_session.add(officer)
    db_session.commit()

    applicant = Applicant(
        full_name="Pooja Sharma",
        phone_number="9876501234",
        pan_number="ABCDE9999F",
        employment_type=EmploymentTypeEnum.SELF_EMPLOYED,
        sub_profile="RETAIL"
    )
    db_session.add(applicant)
    db_session.commit()

    app = Application(
        case_number="APP-SCORING-01",
        applicant_id=applicant.id,
        loan_type="BUSINESS_LOAN",
        requested_amount=300000.0,
        status=ApplicationStatusEnum.PD_IN_PROGRESS
    )
    db_session.add(app)
    db_session.commit()

    session = PDSession(
        application_id=app.id,
        officer_id=officer.id,
        channel="ground",
        status="recorded",
        is_session_active=True
    )
    db_session.add(session)
    db_session.commit()

    return session


def test_officer_score_zero_gaps_gives_100_uptake(db_session, scoring_setup):
    """If no follow-up questions were ever generated, officer should get 100% uptake (not penalized)."""
    session = scoring_setup

    # Add 5 photo categories
    categories = [
        "BUSINESS_EXTERIOR", "BUSINESS_INTERIOR", "MACHINERY_ASSETS",
        "OWNER_AT_PREMISES", "APPLICANT_PORTRAIT"
    ]
    for cat in categories:
        photo = GroundPDPhoto(
            pd_session_id=session.id,
            photo_category=cat,
            file_path=f"/photos/{cat.lower()}.jpg",
            gps_latitude=28.6139,
            gps_longitude=77.2090
        )
        db_session.add(photo)

    # Add extracted field
    ef = ExtractedField(
        pd_session_id=session.id,
        field_name="monthly_turnover",
        value="150000",
        source="stated",
        officer_confirmed=True
    )
    db_session.add(ef)
    db_session.commit()

    score = compute_officer_pd_score(str(session.id), db_session)
    assert score.suggestion_uptake_score == 100.0
    assert score.reconfirmation_diligence_score == 100.0
    assert score.overall_score >= 80.0


def test_officer_score_with_gaps_and_separate_proactive_bonus(db_session, scoring_setup):
    """Verifies that proactive bonus points are kept separate from overall_score."""
    session = scoring_setup

    # Add 2 gap questions: 1 resolved, 1 unresolved -> 50% uptake
    q1 = GapQuestion(pd_session_id=session.id, question_text="Q1", resolved=True)
    q2 = GapQuestion(pd_session_id=session.id, question_text="Q2", resolved=False)
    db_session.add_all([q1, q2])

    # Pre-record 3 proactive bonus points
    existing_score = OfficerPDScore(
        pd_session_id=session.id,
        officer_id=session.officer_id,
        coverage_score=80.0,
        suggestion_uptake_score=50.0,
        reconfirmation_diligence_score=60.0,
        proactive_diligence_bonus=3.0,
        overall_score=65.0
    )
    db_session.add(existing_score)
    db_session.commit()

    score = compute_officer_pd_score(str(session.id), db_session)
    assert score.suggestion_uptake_score == 50.0
    assert score.proactive_diligence_bonus == 3.0  # Kept separate!


def test_customer_consistency_rollup(db_session, scoring_setup):
    session = scoring_setup
    flag = CustomerConsistencyFlag(
        pd_session_id=session.id,
        field_name="monthly_turnover",
        value_a="20L",
        value_b="2k daily",
        severity="high",
        resolution_note="Contradiction flagged for underwriter"
    )
    db_session.add(flag)
    db_session.commit()

    flags = finalize_consistency_flags(str(session.id), db_session)
    assert len(flags) == 1
    assert flags[0].field_name == "monthly_turnover"
    assert flags[0].severity == "high"
