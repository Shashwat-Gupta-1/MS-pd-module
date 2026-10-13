import pytest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_otp,
    verify_otp,
)


class TestSecurityUtilities:
    def test_password_hashing_and_verification(self):
        raw_pw = "creditOfficerPass#2026"
        hashed = hash_password(raw_pw)
        assert hashed != raw_pw
        assert verify_password(raw_pw, hashed) is True
        assert verify_password("wrongPassword", hashed) is False

    def test_jwt_token_encode_decode(self):
        payload = {"sub": "off-12345", "role": "officer", "name": "Rajiv Sharma"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "off-12345"
        assert decoded["role"] == "officer"
        assert decoded["name"] == "Rajiv Sharma"

    def test_otp_flow(self):
        phone = "9876543210"
        otp = generate_otp(phone)
        assert len(otp) == 6
        assert verify_otp(phone, otp) is True
        # Dev fallback test
        assert verify_otp("9999999999", "123456") is True
        assert verify_otp("9999999999", "000000") is False


class TestAuthEndpoints:
    def test_health_check(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["llm_provider"] == "groq"

    def test_send_and_verify_otp(self, client):
        send_res = client.post("/auth/send-otp?phone=9876543210")
        assert send_res.status_code == 200

        verify_res = client.post("/auth/verify-otp", json={"phone": "9876543210", "otp": "123456"})
        assert verify_res.status_code == 200
        assert verify_res.json()["status"] == "verified"

        bad_otp_res = client.post("/auth/verify-otp", json={"phone": "9876543210", "otp": "999999"})
        assert bad_otp_res.status_code == 400

    def test_login_success_and_me_profile(self, client):
        login_res = client.post("/auth/login", json={"phone": "9876543210", "password": "password123"})
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["role"] == "officer"
        token = token_data["access_token"]

        # Call /auth/me with Bearer token
        me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["phone"] == "9876543210"
        assert me_data["role"] == "officer"

    def test_login_failure_wrong_password(self, client):
        res = client.post("/auth/login", json={"phone": "9876543210", "password": "wrongPassword"})
        assert res.status_code == 401

    def test_me_unauthorized_without_token(self, client):
        res = client.get("/auth/me")
        assert res.status_code == 401

    def test_register_officer_and_login(self, client):
        # Register a new field officer
        reg_payload = {
            "name": "Kavita Verma",
            "phone": "9812345678",
            "password": "officerPass123",
            "branch": "Mansarovar Branch",
            "role": "officer"
        }
        reg_res = client.post("/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        assert reg_data["name"] == "Kavita Verma"
        assert reg_data["phone"] == "9812345678"
        assert reg_data["branch"] == "Mansarovar Branch"
        assert reg_data["role"] == "officer"

        # Prevent duplicate mobile number
        dup_res = client.post("/auth/register", json=reg_payload)
        assert dup_res.status_code == 400

        # Login with the newly registered officer credentials
        login_res = client.post("/auth/login", json={
            "phone": "9812345678",
            "password": "officerPass123"
        })
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["name"] == "Kavita Verma"

        # List officers
        list_res = client.get("/auth/officers")
        assert list_res.status_code == 200
        officers = list_res.json()
        assert any(o["phone"] == "9812345678" for o in officers)

