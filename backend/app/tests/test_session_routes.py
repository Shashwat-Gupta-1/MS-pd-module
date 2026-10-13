import pytest
from app.models.applicant import Applicant, EmploymentTypeEnum
from app.models.application import Application, ApplicationStatusEnum
from app.models.officer import Officer
from app.models.ground_pd_photo import GroundPDPhoto
from app.models.extracted_field import ExtractedField


def get_auth_token(client):
    res = client.post("/auth/login", json={"phone": "9876543210", "password": "password123"})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def session_env(db_session, client):
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch current officer
    me_res = client.get("/auth/me", headers=headers)
    officer_id = me_res.json()["id"]

    # Create applicant & application
    applicant = Applicant(
        full_name="Vikram Singh",
        phone_number="9871122334",
        pan_number="ABCDE5555F",
        employment_type=EmploymentTypeEnum.SELF_EMPLOYED,
        sub_profile="RETAIL"
    )
    db_session.add(applicant)
    db_session.commit()

    app = Application(
        case_number="APP-SESSION-TEST",
        applicant_id=applicant.id,
        loan_type="BUSINESS_LOAN",
        requested_amount=400000.0,
        status=ApplicationStatusEnum.LEAD_CREATED
    )
    db_session.add(app)
    db_session.commit()

    return {"headers": headers, "application_id": str(app.id), "officer_id": officer_id}


def test_pd_session_lifecycle_and_endpoints(client, session_env, db_session):
    headers = session_env["headers"]
    app_id = session_env["application_id"]
    off_id = session_env["officer_id"]

    # 1. Start PD Session
    start_payload = {
        "application_id": app_id,
        "officer_id": off_id,
        "consent_captured": True
    }
    start_res = client.post("/pd-sessions", json=start_payload, headers=headers)
    assert start_res.status_code == 201
    session_data = start_res.json()
    session_id = session_data["id"]
    assert session_data["is_session_active"] is True
    assert session_data["consent_captured"] is True

    # 2. Receive transcript batch
    batch_payload = {
        "chunk_sequence": 1,
        "segments": [
            {
                "start_time": 0.0,
                "end_time": 15.0,
                "speaker": "APPLICANT",
                "text": "My monthly turnover is 2,50,000 rupees and profit margin is 12 percent.",
                "confidence": 0.95
            }
        ]
    }
    batch_res = client.post(f"/pd-sessions/{session_id}/batch", json=batch_payload, headers=headers)
    assert batch_res.status_code == 200
    assert isinstance(batch_res.json(), list)

    # 3. Get Live State
    live_res = client.get(f"/pd-sessions/{session_id}/live-state", headers=headers)
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert live_data["session_id"] == session_id
    assert live_data["is_session_active"] is True
    assert "extracted_fields" in live_data

    # 4. Reconfirm numeric field
    reconfirm_payload = {
        "field_name": "monthly_turnover",
        "confirmed_value": "260000",
        "officer_confirmed": True
    }
    reconf_res = client.post(f"/pd-sessions/{session_id}/reconfirm", json=reconfirm_payload, headers=headers)
    assert reconf_res.status_code == 200
    assert reconf_res.json()["value"] == "260000"
    assert reconf_res.json()["officer_confirmed"] is True

    # 5. Manual field entry fallback
    manual_payload = {
        "field_name": "supplier_payment_terms",
        "value": "15 days credit via ledger",
        "reason": "Customer spoke softly"
    }
    manual_res = client.post(f"/pd-sessions/{session_id}/manual-field", json=manual_payload, headers=headers)
    assert manual_res.status_code == 200
    assert manual_res.json()["value"] == "15 days credit via ledger"

    # 6. Submit Officer Remarks
    remarks_payload = {
        "remark_text": "Good shop footfall observed. Shopkeeper has strong neighborhood reputation."
    }
    remarks_res = client.post(f"/pd-sessions/{session_id}/remarks", json=remarks_payload, headers=headers)
    assert remarks_res.status_code == 200
    assert remarks_res.json()["status"] == "success"

    # 7. End PD Session
    # Seed 5 photos so completion gate passes
    categories = [
        "BUSINESS_EXTERIOR", "BUSINESS_INTERIOR", "MACHINERY_ASSETS",
        "OWNER_AT_PREMISES", "APPLICANT_PORTRAIT"
    ]
    for cat in categories:
        photo = GroundPDPhoto(
            pd_session_id=session_id,
            photo_category=cat,
            file_path=f"/photos/{cat.lower()}.jpg",
            gps_latitude=28.6139,
            gps_longitude=77.2090
        )
        db_session.add(photo)
    db_session.commit()

    end_res = client.post(f"/pd-sessions/{session_id}/end", headers=headers)
    assert end_res.status_code == 200
    end_data = end_res.json()
    assert end_data["session_id"] == session_id
    assert "completion_gate" in end_data
    assert "officer_score" in end_data

    # 8. Test Structured Audit Logs Endpoints
    logs_res = client.get(f"/pd-sessions/{session_id}/logs", headers=headers)
    assert logs_res.status_code == 200
    logs_data = logs_res.json()
    assert logs_data["session_id"] == session_id
    assert logs_data["total_events"] >= 2
    assert "summary" in logs_data
    assert "events" in logs_data

    # Verify officer & customer info are captured in summary
    summary = logs_data["summary"]
    assert "officer" in summary
    assert "customer" in summary
    assert summary["customer"]["name"] == "Vikram Singh"

    # Test summary-only endpoint
    summary_res = client.get(f"/pd-sessions/{session_id}/logs/summary", headers=headers)
    assert summary_res.status_code == 200
    assert summary_res.json()["session_id"] == session_id

