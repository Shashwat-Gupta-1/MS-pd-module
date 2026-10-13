import pytest
from app.models.profession_profile import ProfessionProfile
from app.rag.ingest_profession_profiles import ingest_profession_profiles
from app.rag.retrieval import get_profession_profile


def test_ingest_profession_profiles(db_session):
    """Verify that all 5 sub-profile JSON files are ingested idempotently into ProfessionProfile."""
    res = ingest_profession_profiles(db_session)
    assert res["total"] >= 5
    assert res["created"] >= 5

    # Check that manufacturing profile was created
    mfg = db_session.query(ProfessionProfile).filter(ProfessionProfile.sub_profile == "MANUFACTURING").first()
    assert mfg is not None
    assert mfg.display_name == "Manufacturing / Job-Work"
    assert "gross_margin_pct" in mfg.benchmark_margins_json
    assert len(mfg.required_info_checklist_json) > 0
    assert len(mfg.red_flags_json) > 0

    # Idempotent re-run
    res_repeat = ingest_profession_profiles(db_session)
    assert res_repeat["created"] == 0
    assert res_repeat["updated"] >= 5


def test_get_profession_profile_exact_match(db_session):
    """Primary path: exact match on sub_profile."""
    ingest_profession_profiles(db_session)

    retail = get_profession_profile("RETAIL", db_session)
    assert retail is not None
    assert retail.sub_profile == "RETAIL"
    assert "Kirana" in retail.display_name

    # Case insensitivity test
    services = get_profession_profile("services", db_session)
    assert services is not None
    assert services.sub_profile == "SERVICES"


def test_get_profession_profile_similarity_fallback(db_session):
    """Fallback path: vector similarity search on unrecognized sub-profile."""
    ingest_profession_profiles(db_session)

    # Search for an unrecognized query like "shopkeeper" or "kirana store trading"
    profile = get_profession_profile("kirana trading store", db_session)
    assert profile is not None
    assert profile.sub_profile in ["RETAIL", "SERVICES", "MANUFACTURING"]
