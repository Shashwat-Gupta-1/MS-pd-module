"""Wraps the imagehash library for perceptual-hash duplicate photo detection against previously stored photos."""
import io
from typing import Any, BinaryIO, List, Optional, Tuple, Union
import imagehash
from PIL import Image

from app.core.config import settings


def compute_phash(image_bytes: bytes) -> str:
    """Compute a perceptual hash (pHash) string for the given image bytes."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        hash_val = imagehash.phash(image)
        return str(hash_val)
    except Exception:
        # Fallback if unparseable
        return ""


def find_duplicate_photo(
    current_phash: str,
    stored_photos: Union[List[Tuple[str, str]], List[Tuple[str, str, str]]],
    current_application_id: Optional[str] = None,
    threshold: Optional[int] = None,
) -> Any:
    """Check if the photo is identical or near-identical to another photo in the database.
    If called with 3-tuples (photo_id, app_id, phash_str) or with current_application_id provided:
        Returns: (is_duplicate, duplicate_of_photo_id, duplicate_of_app_id, flags)
    If called with 2-tuples (photo_id, phash_str) without application_id (legacy utility signature):
        Returns: (photo_id, distance) if found, else None
    """
    if not current_phash or not stored_photos:
        if stored_photos and len(stored_photos[0]) == 2 and current_application_id is None:
            return None
        return False, None, None, []

    # Check for legacy 2-tuple format: List of (photo_id, phash_str)
    if len(stored_photos[0]) == 2 and current_application_id is None:
        max_dist = threshold if threshold is not None else 5
        best_match = None
        min_dist = float("inf")
        for photo_id, phash_str in stored_photos:
            if not phash_str:
                continue
            try:
                curr_hash_obj = imagehash.hex_to_hash(current_phash)
                stored_hash_obj = imagehash.hex_to_hash(phash_str)
                dist = curr_hash_obj - stored_hash_obj
                if dist <= max_dist and dist < min_dist:
                    min_dist = dist
                    best_match = (photo_id, dist)
            except Exception:
                try:
                    dist = hamming_distance(current_phash, phash_str)
                    if dist <= max_dist and dist < min_dist:
                        min_dist = dist
                        best_match = (photo_id, dist)
                except Exception:
                    continue
        return best_match

    # Standard / Agent 3 user specification: 3-tuples (photo_id, application_id, phash_str)
    max_dist = threshold if threshold is not None else getattr(settings, "photo_hash_threshold", 10)
    try:
        curr_hash_obj = imagehash.hex_to_hash(current_phash)
    except Exception:
        return False, None, None, []

    curr_app_id = current_application_id or ""
    for item in stored_photos:
        if len(item) == 3:
            photo_id, app_id, phash_str = item
        else:
            photo_id, phash_str = item
            app_id = curr_app_id

        if not phash_str:
            continue
        try:
            stored_hash_obj = imagehash.hex_to_hash(phash_str)
            dist = curr_hash_obj - stored_hash_obj  # Hamming distance

            if dist <= max_dist:
                is_cross_application = (app_id != curr_app_id)
                flag = (
                    f"FLAG_RECYCLED_PHOTO_CROSS_APPLICATION_APP_{app_id}"
                    if is_cross_application
                    else f"FLAG_DUPLICATE_PHOTO_SAME_APPLICATION_PHOTO_{photo_id}"
                )
                return True, photo_id, app_id, [flag]
        except Exception:
            continue

    return False, None, None, []


def compute_dhash(image_source: Union[str, bytes, BinaryIO, Image.Image]) -> str:
    """
    Computes a 64-bit difference hash (dHash) for an image.
    Fast, deterministic, and highly resistant to JPEG compression, scaling,
    and minor brightness/contrast shifts.
    """
    if isinstance(image_source, Image.Image):
        img = image_source
        should_close = False
    elif isinstance(image_source, (bytes, bytearray)):
        img = Image.open(io.BytesIO(image_source))
        should_close = True
    elif isinstance(image_source, str):
        img = Image.open(image_source)
        should_close = True
    else:
        img = Image.open(image_source)
        should_close = True

    try:
        resized = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(resized.tobytes())

        difference_bits = 0
        for row in range(8):
            row_start = row * 9
            for col in range(8):
                left_pixel = pixels[row_start + col]
                right_pixel = pixels[row_start + col + 1]
                difference_bits <<= 1
                if left_pixel > right_pixel:
                    difference_bits |= 1

        return f"{difference_bits:016x}"
    finally:
        if should_close:
            img.close()


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Computes the Hamming distance (number of bit differences) between two 64-bit hex hashes.
    Distance ranges from 0 (identical) to 64 (completely inverted).
    """
    if len(hash1) != 16 or len(hash2) != 16:
        raise ValueError(f"Expected 16-character hex hashes, got {len(hash1)} and {len(hash2)}")

    val1 = int(hash1, 16)
    val2 = int(hash2, 16)
    xor_val = val1 ^ val2
    return xor_val.bit_count()


def is_duplicate_or_similar(hash1: str, hash2: str, max_distance: int = 5) -> bool:
    """Returns True if the Hamming distance between two image hashes is <= max_distance."""
    return hamming_distance(hash1, hash2) <= max_distance
