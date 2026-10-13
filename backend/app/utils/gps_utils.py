"""GPS & EXIF helper functions: haversine distance between points, accuracy radius tolerance,
EXIF metadata extraction, and live-camera capture verification.
"""
import io
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from PIL import Image, ExifTags

from app.core.config import settings
from app.models.ground_pd_photo import GroundPDPhoto

EARTH_RADIUS_METERS = 6371000.0


def haversine_distance(
    lat1: float,
    lon1: float = 0.0,
    lat2: float = 0.0,
    lon2: float = 0.0,
    lng1: Optional[float] = None,
    lng2: Optional[float] = None,
) -> float:
    """Calculate the great-circle distance between two points on Earth in meters."""
    actual_lon1 = lng1 if lng1 is not None else lon1
    actual_lon2 = lng2 if lng2 is not None else lon2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(actual_lon2 - actual_lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(EARTH_RADIUS_METERS * c, 2)


def verify_gps_accuracy(accuracy_m: Optional[float], max_accuracy_m: Optional[float] = None) -> Tuple[str, List[str]]:
    """Verify GPS accuracy radius. Returns (gps_status, flags)."""
    threshold = max_accuracy_m or getattr(settings, "gps_max_accuracy_m", 50.0)
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
    threshold = tolerance_m or getattr(settings, "default_distance_tolerance_m", 150.0)
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
        make = str(named_exif.get("Make", "")).strip()
        model = str(named_exif.get("Model", "")).strip()
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
    max_drift = max_drift_sec or getattr(settings, "photo_timestamp_drift_sec", 1800)
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


def check_cluster_tightness(
    photos: Sequence[Union[GroundPDPhoto, Tuple[float, float]]],
    tolerance_m: float = 150.0
) -> bool:
    """
    Validates that all on-site Ground PD photos form a tight cluster at the borrower's
    premises. All pairwise distances among the given photos' lat/lng must be <= tolerance_m
    (default 150.0 meters).
    """
    if not photos or len(photos) <= 1:
        return True

    coords: List[Tuple[float, float]] = []
    for item in photos:
        if isinstance(item, tuple):
            coords.append(item)
        elif hasattr(item, "lat") and hasattr(item, "lng"):
            if item.lat is not None and item.lng is not None:
                coords.append((float(item.lat), float(item.lng)))

    if len(coords) <= 1:
        return True

    n = len(coords)
    for i in range(n):
        lat1, lng1 = coords[i]
        for j in range(i + 1, n):
            lat2, lng2 = coords[j]
            dist = haversine_distance(lat1, lng1, lat2, lng2)
            if dist > tolerance_m:
                return False

    return True


def get_cluster_max_distance(
    photos: Sequence[Union[GroundPDPhoto, Tuple[float, float]]]
) -> float:
    """Returns the maximum pairwise distance in meters among the provided photos."""
    coords: List[Tuple[float, float]] = []
    for item in photos:
        if isinstance(item, tuple):
            coords.append(item)
        elif hasattr(item, "lat") and hasattr(item, "lng"):
            if item.lat is not None and item.lng is not None:
                coords.append((float(item.lat), float(item.lng)))

    if len(coords) <= 1:
        return 0.0

    max_dist = 0.0
    n = len(coords)
    for i in range(n):
        lat1, lng1 = coords[i]
        for j in range(i + 1, n):
            lat2, lng2 = coords[j]
            dist = haversine_distance(lat1, lng1, lat2, lng2)
            if dist > max_dist:
                max_dist = dist

    return max_dist
