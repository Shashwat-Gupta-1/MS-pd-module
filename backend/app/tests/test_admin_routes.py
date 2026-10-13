import pytest
from app.models.officer import Officer
from app.models.applicant import Applicant, EmploymentTypeEnum
from app.models.application import Application, ApplicationStatusEnum
from app.models.pd_session import PDSession
from app.models.officer_pd_score import OfficerPDScore
from app.models.customer_consistency_flag import CustomerConsistencyFlag


def get_auth_token(client):
    res = client.post("/auth/login", json={"phone": "9876543210", "password": "password123"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def admin_data_setup(db_session, client):
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    officer = db_session.query(Officer).filter(Officer.phone == "9876543210").first()
    if not officer:
        from app.core.security import get_password_hash
        officer = Officer(name="Field Officer", phone="9876543210", hashed_password=get_password_hash("password123"), role="ADMIN")
        db_session.add(officer)
        db_session.commit()
    else:
        officer.role = "ADMIN"
        db_session.commit()

    applicant = Applicant(
        full_name="Deepak Joshi",
        phone_number="9877777777",
        pan_number="ABCDE8888F",
        employment_type=EmploymentTypeEnum.SELF_EMPLOYED,
        sub_profile="RETAIL"
    )
    db_session.add(applicant)
    db_session.commit()

    app = Application(
        case_number="APP-ADMIN-01",
        applicant_id=applicant.id,
        loan_type="BUSINESS_LOAN",
        requested_amount=200000.0,
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

    score = OfficerPDScore(
        pd_session_id=session.id,
        officer_id=officer.id,
        coverage_score=90.0,
        suggestion_uptake_score=85.0,
        reconfirmation_diligence_score=100.0,
        proactive_diligence_bonus=5.0,
        overall_score=90.5
    )
    db_session.add(score)

    flag = CustomerConsistencyFlag(
        pd_session_id=session.id,
        field_name="monthly_turnover",
        value_a="5L",
        value_b="1L",
        severity="high",
        resolution_note="Applicant clarified peak vs lean season"
    )
    db_session.add(flag)
    db_session.commit()

    return {"headers": headers, "officer_id": officer.id}


def test_admin_officer_score_analytics(client, admin_data_setup):
    headers = admin_data_setup["headers"]
    res = client.get("/admin/analytics/officer-scores", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_evaluations"] >= 1
    assert data["average_overall_score"] > 0


def test_admin_consistency_flag_analytics(client, admin_data_setup):
    headers = admin_data_setup["headers"]
    res = client.get("/admin/analytics/consistency-flags", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_flags"] >= 1
    assert "severity_breakdown" in data
    assert data["severity_breakdown"]["high"] >= 1


def test_admin_case_funnel_analytics(client, admin_data_setup):
    headers = admin_data_setup["headers"]
    res = client.get("/admin/analytics/case-funnel", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_applications"] >= 1
    assert "funnel_stages" in data


def test_admin_proactive_bonus_leaderboard(client, admin_data_setup):
    headers = admin_data_setup["headers"]
    res = client.get("/admin/analytics/proactive-bonus", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_officers"] >= 1
    assert len(data["leaderboard"]) >= 1
    leader = data["leaderboard"][0]
    assert leader["total_proactive_bonus_points"] >= 5.0
