import os
import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.profession_profile import ProfessionProfile

from app.rag.chroma_client import get_profession_profiles_collection

logger = logging.getLogger(__name__)

PROFILES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "profession_profiles"
)


def ingest_profession_profiles(db: Session, profiles_dir: Optional[str] = None) -> Dict[str, int]:
    """
    Reads all JSON profiles from data/profession_profiles/:
    1. Upserts relational data into the ProfessionProfile table.
    2. Upserts document text and metadata into ChromaDB collection.
    Matches strictly on sub_profile for idempotency.
    """
    target_dir = profiles_dir or PROFILES_DIR
    if not os.path.exists(target_dir):
        logger.warning(f"Profiles directory does not exist: {target_dir}")
        return {"created": 0, "updated": 0, "total": 0}

    created = 0
    updated = 0
    chroma_collection = get_profession_profiles_collection()

    for filename in sorted(os.listdir(target_dir)):
        if not filename.endswith(".json"):
            continue

        file_path = os.path.join(target_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sub_profile = data.get("sub_profile", "").strip().upper()
        if not sub_profile:
            continue

        display_name = data.get("display_name", sub_profile)
        overview = data.get("overview", "")
        benchmark_margins = data.get("benchmark_margins_json", {})
        required_info = data.get("required_info_checklist_json", [])
        red_flags = data.get("red_flags_json", [])

        parent_category = data.get("parent_category", "").strip().upper()
        if not parent_category:
            if "RETAIL" in sub_profile:
                parent_category = "RETAIL"
            elif "MANUFACTURING" in sub_profile or "MFG" in sub_profile:
                parent_category = "MANUFACTURING"
            elif "SERVICES" in sub_profile:
                parent_category = "SERVICES"
            elif "SALARIED" in sub_profile:
                parent_category = "SALARIED"

        # Document text for ChromaDB vector indexing
        embed_text = f"{sub_profile} {display_name}: {overview} Required: {' '.join(required_info)}"

        # 1. Upsert into ChromaDB
        chroma_collection.upsert(
            ids=[sub_profile],
            documents=[embed_text],
            metadatas=[{
                "sub_profile": sub_profile,
                "parent_category": parent_category,
                "display_name": display_name,
                "overview": overview[:500]
            }]
        )

        # 2. Upsert into SQL relational table
        existing = db.query(ProfessionProfile).filter(
            ProfessionProfile.sub_profile == sub_profile
        ).first()

        if existing:
            existing.display_name = display_name
            existing.overview = overview
            existing.benchmark_margins_json = benchmark_margins
            existing.required_info_checklist_json = required_info
            existing.red_flags_json = red_flags
            updated += 1
        else:
            profile = ProfessionProfile(
                sub_profile=sub_profile,
                display_name=display_name,
                overview=overview,
                benchmark_margins_json=benchmark_margins,
                required_info_checklist_json=required_info,
                red_flags_json=red_flags,
            )
            db.add(profile)
            created += 1

    db.commit()
    logger.info(f"Profession profiles ingestion complete: created={created}, updated={updated}")
    return {"created": created, "updated": updated, "total": created + updated}


if __name__ == "__main__":
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        res = ingest_profession_profiles(db)
        print("Ingestion results:", res)
    finally:
        db.close()
