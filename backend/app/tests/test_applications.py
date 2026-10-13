import pytest


def get_auth_token(client):
    """Helper to authenticate and return a valid Bearer token."""
    res = client.post("/auth/login", json={"phone": "9876543210", "password": "password123"})
    assert res.status_code == 200
    return res.json()["access_token"]


class TestApplicantIntake:
    def test_create_and_deduplicate_applicant(self, client):
        token = get_auth_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create applicant
        applicant_payload = {
            "name": "Sunil Kumar Sharma",
            "phone": "9812345678",
            "pan": "ABCDE1234F",
            "aadhaar_number": "123456789012",
            "employment_type": "self_employed",
            "business_category": "retail",
            "employer_type": None
        }
        res = client.post("/applicants/", json=applicant_payload, headers=headers)
        assert res.status_code == 201
        applicant = res.json()
        assert applicant["name"] == "Sunil Kumar Sharma"
        assert applicant["phone"] == "9812345678"
        applicant_id = applicant["id"]

        # 2. De-duplicate: Same phone should fail with 400
        dup_phone = applicant_payload.copy()
        dup_phone["pan"] = "XYZWP9999K"
        res_dup_phone = client.post("/applicants/", json=dup_phone, headers=headers)
        assert res_dup_phone.status_code == 400
        assert "already exists" in res_dup_phone.json()["detail"]

        # 3. De-duplicate: Same PAN should fail with 400
        dup_pan = applicant_payload.copy()
        dup_pan["phone"] = "9899999999"
        res_dup_pan = client.post("/applicants/", json=dup_pan, headers=headers)
        assert res_dup_pan.status_code == 400
        assert "already exists" in res_dup_pan.json()["detail"]

        # 4. Fetch applicant by ID
        get_res = client.get(f"/applicants/{applicant_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Sunil Kumar Sharma"


class TestApplicationLifecycle:
    def test_application_creation_and_status(self, client):
        token = get_auth_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Create base applicant
        app_res = client.post(
            "/applicants/",
            json={
                "name": "Pooja Verma",
                "phone": "9711223344",
                "pan": "PQRST5678M",
                "employment_type": "salaried",
                "employer_type": "salaried_private"
            },
            headers=headers
        )
        assert app_res.status_code == 201
        applicant_id = app_res.json()["id"]

        # Create loan application
        case_payload = {
            "applicant_id": applicant_id,
            "product_type": "Secured Business Loan",
            "requested_amount": 750000.0,
            "tenure": 48,
            "rate": 13.5
        }
        create_case_res = client.post("/applications/", json=case_payload, headers=headers)
        assert create_case_res.status_code == 201
        case_data = create_case_res.json()
        assert case_data["status"] == "INTAKE"
        assert case_data["requested_amount"] == 750000.0
        case_id = case_data["id"]

        # Advance to PD_IN_PROGRESS
        start_res = client.post(f"/applications/{case_id}/start-pd", headers=headers)
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "PD_IN_PROGRESS"


class TestQuestionnaireFromFiles:
    def test_file_driven_questionnaire_retrieval(self, client):
        token = get_auth_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Create self-employed retail applicant
        app_res = client.post(
            "/applicants/",
            json={
                "name": "Ramesh Groceries",
                "phone": "9822334455",
                "employment_type": "self_employed",
                "business_category": "retail"
            },
            headers=headers
        )
        applicant_id = app_res.json()["id"]

        case_res = client.post(
            "/applications/",
            json={
                "applicant_id": applicant_id,
                "product_type": "Retail MSME Loan",
                "requested_amount": 300000.0,
                "tenure": 24,
                "rate": 15.0
            },
            headers=headers
        )
        case_id = case_res.json()["id"]

        # Fetch questionnaire
        q_res = client.get(f"/questionnaire/{case_id}", headers=headers)
        assert q_res.status_code == 200
        data = q_res.json()

        # Check structure
        assert data["application_id"] == case_id
        assert data["employment_type"] == "self_employed"
        assert len(data["tier1_universal"]) == 14
        assert len(data["tier2_branch"]) == 10
        assert len(data["tier3_trade_specific"]) == 8  # Retail has 8 specific baseline questions
        assert data["total_questions_count"] == 32

    def test_hot_reload_questions(self, client):
        token = get_auth_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        reload_res = client.post("/questionnaire/reload", headers=headers)
        assert reload_res.status_code == 200
        res_data = reload_res.json()
        assert res_data["status"] == "success"
        assert res_data["details"]["total_questions_synced"] == 68
