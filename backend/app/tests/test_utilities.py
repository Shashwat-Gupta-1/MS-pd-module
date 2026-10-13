import io
from datetime import datetime, timezone
import pytest
from PIL import Image

from app.utils.image_hash import (
    compute_dhash,
    hamming_distance,
    is_duplicate_or_similar,
    find_duplicate_photo,
)
from app.utils.pii_masking import (
    mask_pan,
    mask_aadhaar,
    mask_phone,
    mask_bank_account,
    mask_pii_text,
    mask_pii_dict,
)
from app.utils.completion_gate import (
    validate_session_completion,
    MANDATORY_PHOTO_CATEGORIES,
)
from app.models.applicant import Applicant
from app.models.application import Application
from app.models.officer import Officer
from app.models.pd_session import PDSession
from app.models.question_bank import QuestionBank
from app.models.extracted_field import ExtractedField
from app.models.gap_question import GapQuestion
from app.models.ground_pd_photo import GroundPDPhoto
from app.services.questionnaire_loader import sync_questions_to_db


# Helper to generate test images in-memory
def create_test_image(color=(255, 0, 0), size=(100, 100)) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestImageHash:
    def test_compute_dhash_returns_16_char_hex(self):
        img_bytes = create_test_image(color=(120, 50, 200))
        dhash = compute_dhash(img_bytes)
        assert isinstance(dhash, str)
        assert len(dhash) == 16
        # Verify valid hex
        int(dhash, 16)

    def test_identical_images_have_zero_hamming_distance(self):
        img_bytes = create_test_image(color=(100, 150, 200))
        hash1 = compute_dhash(img_bytes)
        hash2 = compute_dhash(img_bytes)
        assert hamming_distance(hash1, hash2) == 0
        assert is_duplicate_or_similar(hash1, hash2, max_distance=0)

    def test_similar_resized_images_have_low_distance(self):
        img1 = Image.new("RGB", (200, 200), color=(100, 200, 150))
        buf1 = io.BytesIO()
        img1.save(buf1, format="JPEG", quality=95)

        img2 = img1.resize((150, 150))
        buf2 = io.BytesIO()
        img2.save(buf2, format="JPEG", quality=80)

        hash1 = compute_dhash(buf1.getvalue())
        hash2 = compute_dhash(buf2.getvalue())
        assert hamming_distance(hash1, hash2) <= 5
        assert is_duplicate_or_similar(hash1, hash2, max_distance=5)

    def test_find_duplicate_photo(self):
        img1 = create_test_image((255, 0, 0))
        img2 = create_test_image((0, 255, 0))
        hash1 = compute_dhash(img1)
        hash2 = compute_dhash(img2)

        existing = [("photo_001", hash1)]
        match = find_duplicate_photo(hash1, existing)
        assert match is not None
        assert match[0] == "photo_001"
        assert match[1] == 0


class TestPIIMasking:
    def test_mask_pan(self):
        assert mask_pan("ABCDE1234F") == "XXXXX1234F"
        assert mask_pan("xyzpe5678k") == "XXXXX5678K"
        assert mask_pan("INVALID") == "INVALID"
        assert mask_pan("") == ""

    def test_mask_aadhaar(self):
        assert mask_aadhaar("123456789012") == "XXXXXXXX9012"
        assert mask_aadhaar("1234 5678 9012") == "XXXXXXXX9012"
        assert mask_aadhaar("1234-5678-9012") == "XXXXXXXX9012"
        assert mask_aadhaar("123") == "123"

    def test_mask_phone(self):
        assert mask_phone("9876543210") == "98XXXXXX10"
        assert mask_phone("+919876543210") == "+91 98XXXXXX10"
        assert mask_phone("+91 9876543210") == "+91 98XXXXXX10"

    def test_mask_bank_account(self):
        assert mask_bank_account("123456789012") == "XXXXXXXX9012"
        assert mask_bank_account("987654321") == "XXXXX4321"

    def test_mask_pii_text(self):
        text = "Borrower PAN is ABCDE1234F and mobile number is 9876543210 with Aadhaar 1234 5678 9012."
        masked = mask_pii_text(text)
        assert "ABCDE1234F" not in masked
        assert "XXXXX1234F" in masked
        assert "9876543210" not in masked
        assert "98XXXXXX10" in masked
        assert "XXXXXXXX9012" in masked

    def test_mask_pii_dict(self):
        data = {
            "borrower_name": "Ramesh Kumar",
            "pan_number": "ABCDE1234F",
            "mobile_phone": "9876543210",
            "bank_account_no": "123456789012",
            "notes": "Verified PAN ABCDE1234F in person."
        }
        masked = mask_pii_dict(data)
        assert masked["pan_number"] == "XXXXX1234F"
        assert masked["mobile_phone"] == "98XXXXXX10"
        assert masked["bank_account_no"] == "XXXXXXXX9012"
        assert "ABCDE1234F" not in masked["notes"]
        assert "XXXXX1234F" in masked["notes"]


class TestCompletionGate:
    def test_completion_gate_fails_when_session_not_found(self, db_session):
        res = validate_session_completion(db_session, "non_existent_id")
        assert not res.is_complete
        assert not res.can_submit
        assert "PD Session not found" in res.blocking_reasons[0]

    def test_completion_gate_blocks_incomplete_session(self, db_session):
        # 1. Load questions into DB
        sync_questions_to_db(db_session)

        # 2. Setup officer, applicant, application, session
        officer = Officer(
            name="Verification Officer",
            phone="8888877777",
            hashed_password="hash",
            role="officer"
        )
        db_session.add(officer)
        db_session.flush()

        applicant = Applicant(
            name="Test Borrower",
            phone="7777766666",
            employment_type="self_employed",
            business_category="retail"
        )
        db_session.add(applicant)
        db_session.flush()

        app = Application(
            applicant_id=applicant.id,
            product_type="business_loan",
            requested_amount=1000000.0,
            tenure=36,
            rate=14.0,
            status="PD_IN_PROGRESS"
        )
        db_session.add(app)
        db_session.flush()

        session = PDSession(
            application_id=app.id,
            officer_id=officer.id,
            channel="ground",
            status="recorded"
        )
        db_session.add(session)
        db_session.commit()

        # Gate check should fail because:
        # - Mandatory questionnaire incomplete
        # - Missing 5 mandatory photos
        # - Financial reconfirmation missing
        res = validate_session_completion(db_session, session.id)
        assert not res.is_complete
        assert not res.can_submit
        assert len(res.blocking_reasons) >= 2
        assert any("Mandatory questionnaire incomplete" in r for r in res.blocking_reasons)
        assert any("Missing 5 mandatory photo categories" in r for r in res.blocking_reasons)

    def test_completion_gate_passes_when_all_requirements_met(self, db_session):
        # 1. Load questions into DB
        sync_questions_to_db(db_session)

        # 2. Setup officer, applicant, application
        officer = Officer(
            name="Gate Officer",
            phone="8888811111",
            hashed_password="hash",
            role="officer"
        )
        db_session.add(officer)
        db_session.flush()

        applicant = Applicant(
            name="Fully Qualified Borrower",
            phone="7777711111",
            employment_type="self_employed",
            business_category="retail"
        )
        db_session.add(applicant)
        db_session.flush()

        app = Application(
            applicant_id=applicant.id,
            product_type="business_loan",
            requested_amount=500000.0,
            tenure=24,
            rate=13.5,
            status="PD_IN_PROGRESS"
        )
        db_session.add(app)
        db_session.flush()

        session = PDSession(
            application_id=app.id,
            officer_id=officer.id,
            channel="ground",
            status="recorded"
        )
        db_session.add(session)
        db_session.flush()

        # 3. Satisfy all mandatory questionnaire questions
        # Fetch all mandatory questions for Tier 1, Tier 2 (self_employed), Tier 3 (retail)
        t1 = db_session.query(QuestionBank).filter(QuestionBank.tier == 1, QuestionBank.is_mandatory == True).all()
        t2 = db_session.query(QuestionBank).filter(QuestionBank.tier == 2, QuestionBank.employment_type == "self_employed", QuestionBank.is_mandatory == True).all()
        t3 = db_session.query(QuestionBank).filter(QuestionBank.tier == 3, QuestionBank.business_category == "retail", QuestionBank.is_mandatory == True).all()

        for q in t1 + t2 + t3:
            ef = ExtractedField(
                pd_session_id=session.id,
                field_name=q.field_name,
                value="Verified statement answer",
                source="stated",
                officer_confirmed=True
            )
            db_session.add(ef)

        # Also add a turnover / income confirmation field
        ef_turnover = ExtractedField(
            pd_session_id=session.id,
            field_name="monthly_turnover",
            value="450000",
            source="stated",
            officer_confirmed=True
        )
        db_session.add(ef_turnover)

        # 4. Add all 5 mandatory photo categories
        now = datetime.now(timezone.utc)
        for cat in MANDATORY_PHOTO_CATEGORIES:
            photo = GroundPDPhoto(
                application_id=app.id,
                category=cat,
                url=f"/media/photos/{cat.lower()}.jpg",
                lat=28.6139,
                lng=77.2090,
                captured_at=now
            )
            db_session.add(photo)

        # 5. Add a resolved gap question
        gap = GapQuestion(
            pd_session_id=session.id,
            question_text="Follow-up on supplier payment terms",
            round_number=1,
            resolved=True,
            answer="15 days credit"
        )
        db_session.add(gap)

        db_session.commit()

        # Run completion gate
        res = validate_session_completion(db_session, session.id)
        assert res.is_complete is True
        assert res.can_submit is True
        assert res.completion_percentage == 100.0
        assert len(res.blocking_reasons) == 0
