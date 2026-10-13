import os
import logging
from typing import Optional
from pathlib import Path
import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from app.core.config import settings

logger = logging.getLogger(__name__)

_client_instance: Optional[ClientAPI] = None
PROFESSION_PROFILES_COLLECTION = "profession_profiles"


def get_chroma_client(
    persist_directory: Optional[Path] = None,
    ephemeral: Optional[bool] = None
) -> ClientAPI:
    """
    Returns a ChromaDB client instance.
    Uses EphemeralClient in test environments or when explicitly requested,
    otherwise uses PersistentClient with settings.CHROMA_PERSIST_DIRECTORY.
    """
    global _client_instance

    is_test_env = (
        ephemeral is True
        or os.getenv("TESTING", "").lower() in ("1", "true", "yes")
        or os.getenv("CHROMA_EPHEMERAL", "").lower() in ("1", "true", "yes")
    )

    if is_test_env:
        return chromadb.EphemeralClient()

    if _client_instance is None:
        target_dir = persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        os.makedirs(target_dir, exist_ok=True)
        _client_instance = chromadb.PersistentClient(path=str(target_dir))
        logger.info(f"Initialized ChromaDB PersistentClient at {target_dir}")

    return _client_instance


def get_profession_profiles_collection(client: Optional[ClientAPI] = None) -> Collection:
    """
    Returns the 'profession_profiles' collection configured with cosine distance space.
    """
    chroma_client = client or get_chroma_client()
    collection = chroma_client.get_or_create_collection(
        name=PROFESSION_PROFILES_COLLECTION,
        metadata={"hnsw:space": "cosine"}
    )
    return collection


def reset_chroma_client() -> None:
    """Resets the singleton client instance (useful in test fixtures)."""
    global _client_instance
    _client_instance = None
