"""Wraps the imagehash library for perceptual-hash duplicate photo detection against previously stored photos."""
import io
from typing import List, Optional, Tuple
import imagehash
from PIL import Image

from app.core.config import settings


def compute_phash(image_bytes: bytes) -> str:
    """Compute a perceptual hash (pHash) string for the given image bytes."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        hash_val = imagehash.phash(image)
        return str(hash_val)
    except Exception as e:
        # Fallback if unparseable
        return ""


def find_duplicate_photo(
    current_phash: str,
    stored_photos: List[Tuple[str, str, str]],  # List of (photo_id, application_id, phash_str)
    current_application_id: str,
    threshold: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[str], List[str]]:
    """Check if the photo is identical or near-identical to another photo in the database.
    Returns: (is_duplicate, duplicate_of_photo_id, duplicate_of_app_id, flags)
    """
    if not current_phash:
        return False, None, None, []

    max_dist = threshold if threshold is not None else settings.photo_hash_threshold
    try:
        curr_hash_obj = imagehash.hex_to_hash(current_phash)
    except Exception:
        return False, None, None, []

    for photo_id, app_id, phash_str in stored_photos:
        if not phash_str:
            continue
        try:
            stored_hash_obj = imagehash.hex_to_hash(phash_str)
            dist = curr_hash_obj - stored_hash_obj  # Hamming distance

            if dist <= max_dist:
                is_cross_application = (app_id != current_application_id)
                flag = (
                    f"FLAG_RECYCLED_PHOTO_CROSS_APPLICATION_APP_{app_id}"
                    if is_cross_application
                    else f"FLAG_DUPLICATE_PHOTO_SAME_APPLICATION_PHOTO_{photo_id}"
                )
                return True, photo_id, app_id, [flag]
        except Exception:
            continue

    return False, None, None, []
