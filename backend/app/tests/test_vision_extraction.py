import io
from datetime import datetime, timezone, timedelta
from PIL import Image

from app.models.ground_pd_photo import GroundPDPhoto
from app.models.photo_extraction import PhotoExtraction
from app.models.asset_valuation import AssetValuation
from app.models.business_estimate import BusinessEstimate
from app.models.applicant import Applicant
from app.models.application import Application
from app.agents.vision_extraction import (
    extract_photo_vision,
    aggregate_application_assets,
    verify_photo_gps_cluster,
    process_and_save_photo_extraction,
)
from app.utils.gps_utils import (
    haversine_distance,
    verify_gps_accuracy,
    check_site_distance,
    extract_exif_metadata,
    verify_live_capture,
)
from app.utils.image_hash import compute_phash, find_duplicate_photo
from app.workers.tasks import extract_photo_vision_task


def test_extract_photo_vision(tmp_path):
    # Create a dummy image file
    test_img = tmp_path / "test_photo.jpg"
    test_img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00")

    result = extract_photo_vision(
        photo_path=str(test_img),
        category="MACHINERY_ASSETS",
        occupation_name="Kirana Store",
        category_hints="Verify weighing scale and refrigerator",
    )

    assert isinstance(result, dict)
    assert "items" in result
    assert "estimated_total_value_min" in result
    assert "estimated_total_value_max" in result
    assert result["estimated_total_value_min"] >= 0
    assert result["estimated_total_value_max"] >= result["estimated_total_value_min"]
    if result["items"]:
        item = result["items"][0]
        assert "name" in item
        assert "count" in item
        assert "condition" in item
        assert "unit_value_min_inr" in item
        assert "unit_value_max_inr" in item


def test_aggregate_application_assets(db_session):
    # Setup applicant & application
    applicant = Applicant(
        full_name="Rajesh Kumar",
        phone_number="9876543210",
        employment_type="self_employed",
        business_category="RETAIL",
        sub_profile="RETAIL"
    )
    db_session.add(applicant)
    db_session.commit()

    application = Application(
        applicant_id=applicant.id,
        loan_type="BL",
        requested_amount=300000.0,
        status="DRAFT"
    )
    db_session.add(application)
    db_session.commit()

    # Photo 1: Machinery
    p1 = GroundPDPhoto(
        application_id=application.id,
        category="MACHINERY_ASSETS",
        url="/media/photos/test1.jpg",
        lat=26.9124,
        lng=75.7873
    )
    db_session.add(p1)
    db_session.commit()

    pe1 = PhotoExtraction(
        photo_id=p1.id,
        category_matches_photo=True,
        premises_type="retail_shop",
        stock_level="high",
        items=[
            {
                "name": "Digital Weighing Scale",
                "count": 2,
                "condition": "good",
                "unit_value_min_inr": 3000.0,
                "unit_value_max_inr": 5000.0,
                "total_value_min_inr": 6000.0,
                "total_value_max_inr": 10000.0
            }
        ],
        estimated_total_value_min=6000.0,
        estimated_total_value_max=10000.0
    )
    db_session.add(pe1)

    # Photo 2: Stock
    p2 = GroundPDPhoto(
        application_id=application.id,
        category="STOCK_INVENTORY",
        url="/media/photos/test2.jpg",
        lat=26.9125,
        lng=75.7874
    )
    db_session.add(p2)
    db_session.commit()

    pe2 = PhotoExtraction(
        photo_id=p2.id,
        category_matches_photo=True,
        premises_type="retail_shop",
        stock_level="medium",
        items=[
            {
                "name": "Packaged FMCG Stock",
                "count": 1,
                "condition": "good",
                "unit_value_min_inr": 40000.0,
                "unit_value_max_inr": 60000.0,
                "total_value_min_inr": 40000.0,
                "total_value_max_inr": 60000.0
            }
        ],
        estimated_total_value_min=40000.0,
        estimated_total_value_max=60000.0
    )
    db_session.add(pe2)
    db_session.commit()

    # Run aggregation
    summary = aggregate_application_assets(application.id, db_session)

    assert "assets" in summary
    assert len(summary["assets"]) == 2
    assert summary["total_asset_value_min_inr"] == 46000.0
    assert summary["total_asset_value_max_inr"] == 70000.0

    # Verify persisted AssetValuation rows
    saved = db_session.query(AssetValuation).filter_by(application_id=application.id).all()
    assert len(saved) == 2

    # Verify BusinessEstimate upserted
    best = db_session.query(BusinessEstimate).filter_by(application_id=application.id).first()
    assert best is not None
    assert best.total_physical_assets_min == 46000.0
    assert best.total_physical_assets_max == 70000.0
    assert best.estimated_stock_value == 50000.0  # midpoint of 40k-60k
    assert best.estimated_machinery_value == 8000.0  # midpoint of 6k-10k


def test_verify_photo_gps_cluster(db_session):
    applicant = Applicant(full_name="Sunil Sharma", phone_number="9876543211", employment_type="self_employed")
    db_session.add(applicant)
    db_session.commit()

    app = Application(applicant_id=applicant.id, loan_type="BL", requested_amount=200000.0)
    db_session.add(app)
    db_session.commit()

    # Add 2 photos close together (within 20 meters)
    p1 = GroundPDPhoto(application_id=app.id, category="BUSINESS_EXTERIOR", url="/test1.jpg", lat=26.9124, lng=75.7873)
    p2 = GroundPDPhoto(application_id=app.id, category="BUSINESS_INTERIOR", url="/test2.jpg", lat=26.9125, lng=75.7874)
    db_session.add_all([p1, p2])
    db_session.commit()

    gps_res = verify_photo_gps_cluster(app.id, db_session, tolerance_m=150.0)
    assert gps_res["within_tolerance"] is True
    assert gps_res["status"] == "PASS"
    assert gps_res["photo_count"] == 2


def test_ground_pd_api_routes(client, db_session):
    # Authenticate officer
    res = client.post("/auth/login", json={"phone": "9876543210", "password": "password123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup applicant & application
    applicant = Applicant(
        full_name="Mohan Lal",
        phone_number="9876543212",
        employment_type="self_employed",
        business_category="MANUFACTURING"
    )
    db_session.add(applicant)
    db_session.commit()

    app = Application(
        applicant_id=applicant.id,
        loan_type="BL",
        requested_amount=500000.0,
        status="DRAFT"
    )
    db_session.add(app)
    db_session.commit()

    # Create photo with extraction
    photo = GroundPDPhoto(
        application_id=app.id,
        category="MACHINERY_ASSETS",
        url="/media/photos/lathe_test.jpg",
        lat=26.9124,
        lng=75.7873
    )
    db_session.add(photo)
    db_session.commit()

    pe = PhotoExtraction(
        photo_id=photo.id,
        category_matches_photo=True,
        premises_type="workshop",
        stock_level="medium",
        items=[
            {
                "name": "Lathe Machine Heavy Duty",
                "count": 1,
                "condition": "good",
                "unit_value_min_inr": 150000.0,
                "unit_value_max_inr": 200000.0,
                "total_value_min_inr": 150000.0,
                "total_value_max_inr": 200000.0
            }
        ],
        estimated_total_value_min=150000.0,
        estimated_total_value_max=200000.0
    )
    db_session.add(pe)
    db_session.commit()

    # Trigger aggregate API
    agg_res = client.post(f"/ground-pd/applications/{app.id}/aggregate", headers=headers)
    assert agg_res.status_code == 200
    agg_data = agg_res.json()
    assert agg_data["status"] == "success"
    assert agg_data["result"]["total_asset_value_min_inr"] == 150000.0

    # Query assets API
    assets_res = client.get(f"/ground-pd/applications/{app.id}/assets", headers=headers)
    assert assets_res.status_code == 200
    assets_data = assets_res.json()
    assert assets_data["asset_count"] == 1
    assert assets_data["assets"][0]["item_name"] == "Lathe Machine Heavy Duty"
    assert assets_data["business_estimate"]["total_physical_assets_min"] == 150000.0
    assert assets_data["gps_cluster"]["within_tolerance"] is True

    # Query GPS verify API
    gps_verify_res = client.get(f"/ground-pd/applications/{app.id}/gps-verify", headers=headers)
    assert gps_verify_res.status_code == 200
    assert gps_verify_res.json()["status"] == "PASS"


def test_haversine_and_gps_accuracy():
    # 1. Haversine distance
    d_same = haversine_distance(26.9124, 75.7873, 26.9124, 75.7873)
    assert d_same == 0.0

    d_offset = haversine_distance(26.9124, 75.7873, 26.9130, 75.7873)
    assert 60.0 <= d_offset <= 75.0

    # 2. GPS accuracy
    status_ok, flags_ok = verify_gps_accuracy(15.0, max_accuracy_m=50.0)
    assert status_ok == "VALID"
    assert flags_ok == []

    status_poor, flags_poor = verify_gps_accuracy(80.0, max_accuracy_m=50.0)
    assert status_poor == "POOR_ACCURACY"
    assert "FLAG_POOR_GPS_ACCURACY_RADIUS_80M" in flags_poor

    status_none, flags_none = verify_gps_accuracy(None)
    assert status_none == "NO_GPS_ACCURACY_INFO"
    assert "FLAG_MISSING_GPS_ACCURACY" in flags_none

    # 3. Check site distance
    dist, stat, flags = check_site_distance(26.9124, 75.7873, 26.9124, 75.7873, tolerance_m=150.0)
    assert dist == 0.0
    assert stat == "VALID"
    assert flags == []

    dist_far, stat_far, flags_far = check_site_distance(26.9124, 75.7873, 27.0500, 75.7873, tolerance_m=150.0)
    assert dist_far > 150.0
    assert stat_far == "DISTANCE_MISMATCH"
    assert any("FLAG_GPS_LOCATION_MISMATCH" in fl for fl in flags_far)

    dist_missing, stat_missing, flags_missing = check_site_distance(None, None, 26.9124, 75.7873)
    assert dist_missing is None
    assert stat_missing == "NO_GPS"
    assert "FLAG_PHOTO_MISSING_GPS" in flags_missing

    dist_no_site, stat_no_site, _ = check_site_distance(26.9124, 75.7873, None, None)
    assert dist_no_site is None
    assert stat_no_site == "NO_SITE_COORDINATES"


def test_exif_and_live_capture():
    # 1. Non-image bytes or empty exif
    meta = extract_exif_metadata(b"invalid image bytes")
    assert meta["has_exif"] is False
    assert meta["captured_at"] is None
    assert meta["device_model"] is None

    # 2. Verify live capture without EXIF (fallback advisory)
    is_live, cap_dt, dev_model, flags = verify_live_capture(meta)
    assert is_live is True
    assert "FLAG_NO_EXIF_METADATA" in flags

    # 3. Recent capture within allowable drift
    now = datetime.now(timezone.utc)
    fresh_meta = {
        "has_exif": True,
        "captured_at": now - timedelta(minutes=5),
        "device_model": "Samsung Galaxy S23",
    }
    is_live_fresh, _, dev_fresh, flags_fresh = verify_live_capture(fresh_meta, max_drift_sec=1800)
    assert is_live_fresh is True
    assert dev_fresh == "Samsung Galaxy S23"
    assert flags_fresh == []

    # 4. Old gallery upload exceeding drift
    old_meta = {
        "has_exif": True,
        "captured_at": now - timedelta(hours=3),
        "device_model": "Apple iPhone 14",
    }
    is_live_old, _, dev_old, flags_old = verify_live_capture(old_meta, max_drift_sec=1800)
    assert is_live_old is False
    assert dev_old == "Apple iPhone 14"
    assert any("FLAG_SUSPECTED_GALLERY_UPLOAD_TIME_DRIFT" in fl for fl in flags_old)


def test_image_hash_perceptual_hash_and_duplicates():
    # Create simple dummy images
    img1 = Image.new("RGB", (64, 64), color=(200, 50, 50))
    buf1 = io.BytesIO()
    img1.save(buf1, format="JPEG")
    b1 = buf1.getvalue()

    h1 = compute_phash(b1)
    assert isinstance(h1, str)
    assert len(h1) > 0

    # Intra-application duplicate
    stored = [("photo_101", "app_alpha", h1)]
    is_dup, dup_p, dup_a, flags = find_duplicate_photo(h1, stored, current_application_id="app_alpha")
    assert is_dup is True
    assert dup_p == "photo_101"
    assert dup_a == "app_alpha"
    assert any("FLAG_DUPLICATE_PHOTO_SAME_APPLICATION_PHOTO_photo_101" in fl for fl in flags)

    # Cross-application recycled photo
    is_dup_cross, dup_px, dup_ax, flags_x = find_duplicate_photo(h1, stored, current_application_id="app_beta")
    assert is_dup_cross is True
    assert dup_px == "photo_101"
    assert dup_ax == "app_alpha"
    assert any("FLAG_RECYCLED_PHOTO_CROSS_APPLICATION_APP_app_alpha" in fl for fl in flags_x)

    # Non-duplicate
    is_dup_none, _, _, flags_none = find_duplicate_photo("", stored, current_application_id="app_beta")
    assert is_dup_none is False
    assert flags_none == []


def test_extract_photo_vision_task_celery(tmp_path, db_session):
    # Setup applicant & application
    applicant = Applicant(
        full_name="Deepak Verma",
        phone_number="9876543299",
        employment_type="self_employed",
        business_category="RETAIL"
    )
    db_session.add(applicant)
    db_session.commit()

    app = Application(
        applicant_id=applicant.id,
        loan_type="BL",
        requested_amount=250000.0,
        status="DRAFT"
    )
    db_session.add(app)
    db_session.commit()

    # Create dummy photo on disk
    photo_file = tmp_path / "deepak_shop.jpg"
    img = Image.new("RGB", (100, 100), color=(120, 180, 200))
    img.save(str(photo_file), format="JPEG")

    photo = GroundPDPhoto(
        application_id=app.id,
        category="STOCK_INVENTORY",
        url=str(photo_file),
        lat=26.9124,
        lng=75.7873,
        accuracy_radius=12.0
    )
    db_session.add(photo)
    db_session.commit()

    # Run celery task synchronously (Celery @celery_app.task callable)
    res = extract_photo_vision_task(photo.id, db=db_session)
    assert res["status"] == "success"
    assert res["photo_id"] == photo.id

    # Verify updated database fields
    db_session.refresh(photo)
    assert photo.phash is not None
    assert photo.is_live_capture is not None
    assert photo.gps_accuracy_status == "VALID"

    # Verify extraction persisted
    pe = db_session.query(PhotoExtraction).filter_by(photo_id=photo.id).first()
    assert pe is not None
    assert pe.category_matches_photo is True


def test_ground_pd_async_endpoint(client, db_session, tmp_path):
    res = client.post("/auth/login", json={"phone": "9876543210", "password": "password123"})
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    applicant = Applicant(full_name="Sanjay Rao", phone_number="9876543298", employment_type="self_employed")
    db_session.add(applicant)
    db_session.commit()

    app = Application(applicant_id=applicant.id, loan_type="BL", requested_amount=150000.0)
    db_session.add(app)
    db_session.commit()

    photo_file = tmp_path / "sanjay_stock.jpg"
    img = Image.new("RGB", (80, 80), color=(100, 200, 100))
    img.save(str(photo_file), format="JPEG")

    photo = GroundPDPhoto(
        application_id=app.id,
        category="STOCK_INVENTORY",
        url=str(photo_file),
        lat=26.9124,
        lng=75.7873
    )
    db_session.add(photo)
    db_session.commit()

    async_res = client.post(f"/ground-pd/photos/{photo.id}/extract-async", headers=headers)
    assert async_res.status_code == 200
    data = async_res.json()
    assert data["status"] in ["queued", "completed_fallback_sync"]
    assert data["photo_id"] == photo.id

