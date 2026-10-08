"""GPS & EXIF helper functions: haversine distance between points, accuracy radius tolerance,
EXIF metadata extraction, and live-camera capture verification.
"""
import io
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image, ExifTags

from app.core.config import settings


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in meters."""
    r = 6371000.0  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


def verify_gps_accuracy(accuracy_m: Optional[float], max_accuracy_m: Optional[float] = None) -> Tuple[str, List[str]]:
    """Verify GPS accuracy radius. Returns (gps_status, flags)."""
    threshold = max_accuracy_m or settings.gps_max_accuracy_m
    flags = []
    if accuracy_m is None:
        return "NO_GPS_ACCURACY_INFO", ["FLAG_MISSING_GPS_ACCURACY"]
    if accuracy_m > threshold:
        flags.append(f"FLAG_POOR_GPS_ACCURACY_RADIUS_{round(accuracy_m)}M")
        return "POOR_ACCURACY", flags
    return "VALID", flags


def check_site_distance(
    photo_lat: Optional[float],
    photo_lng: Optional[float],
    site_lat: Optional[float],
    site_lng: Optional[float],
    tolerance_m: Optional[float] = None,
) -> Tuple[Optional[float], str, List[str]]:
    """Verify if photo was taken at the declared business or collateral site.
    Returns (distance_m, status, flags).
    """
    if photo_lat is None or photo_lng is None:
        return None, "NO_GPS", ["FLAG_PHOTO_MISSING_GPS"]
    if site_lat is None or site_lng is None:
        return None, "NO_SITE_COORDINATES", []

    dist = haversine_distance(photo_lat, photo_lng, site_lat, site_lng)
    threshold = tolerance_m or settings.default_distance_tolerance_m
    flags = []

    if dist > threshold:
        flags.append(f"FLAG_GPS_LOCATION_MISMATCH_{round(dist)}M_FROM_SITE")
        return dist, "DISTANCE_MISMATCH", flags

    return dist, "VALID", []


def extract_exif_metadata(image_bytes: bytes) -> Dict[str, Any]:
    """Extract EXIF metadata tags including capture time and camera model."""
    meta: Dict[str, Any] = {
        "captured_at": None,
        "device_model": None,
        "has_exif": False,
    }
    try:
        image = Image.open(io.BytesIO(image_bytes))
        exif_raw = image._getexif()
        if not exif_raw:
            return meta

        meta["has_exif"] = True
        named_exif = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}

        # Camera make and model
        make = named_exif.get("Make", "")
        model = named_exif.get("Model", "")
        if make or model:
            meta["device_model"] = f"{make} {model}".strip()

        # Capture timestamp (DateTimeOriginal or DateTime)
        dt_str = named_exif.get("DateTimeOriginal") or named_exif.get("DateTime")
        if dt_str and isinstance(dt_str, str):
            try:
                # Standard EXIF format: "YYYY:MM:DD HH:MM:SS"
                parsed_dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
                meta["captured_at"] = parsed_dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass

    except Exception:
        pass

    return meta


def verify_live_capture(
    exif_meta: Dict[str, Any],
    max_drift_sec: Optional[int] = None,
) -> Tuple[bool, Optional[datetime], Optional[str], List[str]]:
    """Verify whether photo is a fresh live camera capture or an old/gallery photo."""
    flags = []
    max_drift = max_drift_sec or settings.photo_timestamp_drift_sec
    captured_at = exif_meta.get("captured_at")
    device_model = exif_meta.get("device_model")
    has_exif = exif_meta.get("has_exif", False)

    now_utc = datetime.now(timezone.utc)

    if not has_exif or not captured_at:
        # Many web uploads / compressed images strip EXIF, so we flag as advisory without blocking
        flags.append("FLAG_NO_EXIF_METADATA")
        return True, now_utc, device_model, flags

    drift_sec = abs((now_utc - captured_at).total_seconds())
    if drift_sec > max_drift:
        flags.append(f"FLAG_SUSPECTED_GALLERY_UPLOAD_TIME_DRIFT_{round(drift_sec / 60)}MIN")
        return False, captured_at, device_model, flags

    return True, captured_at, device_model, flags
