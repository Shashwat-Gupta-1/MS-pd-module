import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models.profession_profile import ProfessionProfile
from app.rag.chroma_client import get_profession_profiles_collection

logger = logging.getLogger(__name__)


def get_profession_profile(sub_profile: str, db: Session) -> Optional[ProfessionProfile]:
    """
    Retrieves the ProfessionProfile for a given sub_profile.
    
    Primary path: Exact match on sub_profile in the SQL database.
    Fallback path: Semantic vector similarity search via ChromaDB if sub_profile
    is unrecognized, missing, or has no exact match.
    """
    if not sub_profile:
        return None

    cleaned_sub_profile = sub_profile.strip().upper()

    # 0. Auto-seed if database has no profiles loaded yet
    if db.query(ProfessionProfile).count() == 0:
        try:
            from app.rag.ingest_profession_profiles import ingest_profession_profiles
            ingest_profession_profiles(db)
        except Exception as e:
            logger.warning(f"Auto-ingest profession profiles failed: {e}")

    # 1. Primary path: Exact match
    profile = db.query(ProfessionProfile).filter(
        ProfessionProfile.sub_profile == cleaned_sub_profile
    ).first()
    if profile:
        return profile

    # Also check case-insensitive match
    profile = db.query(ProfessionProfile).filter(
        ProfessionProfile.sub_profile.ilike(cleaned_sub_profile)
    ).first()
    if profile:
        return profile

    # 2. Fallback: ChromaDB semantic vector search
    logger.info(f"Sub-profile '{sub_profile}' not found via exact match; querying ChromaDB.")
    try:
        collection = get_profession_profiles_collection()
        results = collection.query(query_texts=[sub_profile], n_results=1)
        if results and results.get("ids") and len(results["ids"]) > 0 and len(results["ids"][0]) > 0:
            matched_id = results["ids"][0][0]
            matched_profile = db.query(ProfessionProfile).filter(
                ProfessionProfile.sub_profile == matched_id
            ).first()
            if matched_profile:
                return matched_profile
    except Exception as e:
        logger.warning(f"ChromaDB similarity search failed: {e}")

    return None


def resolve_granular_sub_profile(
    parent_category: str,
    occupation_text: str,
    db: Session
) -> Optional[ProfessionProfile]:
    """
    Given a high-level parent category (e.g. 'RETAIL', 'SERVICES', 'MANUFACTURING')
    and the borrower's voice-extracted trade/occupation description (e.g. 'cloth store, sarees', 'milk dairy collection'):
    Uses ChromaDB vector similarity to resolve the best granular micro-trade profile.
    Falls back to parent category profile if no granular match is found.
    """
    if not occupation_text or not occupation_text.strip():
        return get_profession_profile(parent_category, db)

    cleaned_parent = (parent_category or "").strip().upper()
    norm_parent = (
        "RETAIL" if "RETAIL" in cleaned_parent or "TRADING" in cleaned_parent else
        "SERVICES" if "SERVICES" in cleaned_parent or "REPAIR" in cleaned_parent else
        "MANUFACTURING" if "MANUFACTURING" in cleaned_parent or "MFG" in cleaned_parent or "JOB" in cleaned_parent else
        cleaned_parent
    )

    # 0. Ensure ChromaDB has profiles loaded
    if db.query(ProfessionProfile).count() == 0:
        try:
            from app.rag.ingest_profession_profiles import ingest_profession_profiles
            ingest_profession_profiles(db)
        except Exception as e:
            logger.warning(f"Auto-ingest profession profiles failed: {e}")

    query_str = f"{norm_parent} {occupation_text.strip()}"
    try:
        collection = get_profession_profiles_collection()
        where_filter = {"parent_category": norm_parent} if norm_parent in ("RETAIL", "SERVICES", "MANUFACTURING", "SALARIED") else None
        
        query_kwargs = {"query_texts": [query_str], "n_results": 1}
        results = None
        if where_filter:
            try:
                results = collection.query(where=where_filter, **query_kwargs)
            except Exception:
                results = collection.query(**query_kwargs)
        else:
            results = collection.query(**query_kwargs)

        if results and results.get("ids") and len(results["ids"]) > 0 and len(results["ids"][0]) > 0:
            matched_id = results["ids"][0][0]
            matched_profile = db.query(ProfessionProfile).filter(
                ProfessionProfile.sub_profile == matched_id
            ).first()
            if matched_profile:
                logger.info(f"Resolved granular trade profile: '{matched_id}' for occupation '{occupation_text}' (parent: {norm_parent})")
                return matched_profile
    except Exception as e:
        logger.warning(f"resolve_granular_sub_profile ChromaDB search failed: {e}")

    # Fallback to parent profile
    return get_profession_profile(parent_category, db)

