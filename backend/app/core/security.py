from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings

# In-memory OTP cache for MVP (simulated SMS gateway)
_otp_store: Dict[str, str] = {}


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


get_password_hash = hash_password


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_otp(phone: str) -> str:
    """Generate and store a 6-digit OTP for simulated phone verification."""
    # For MVP / development, standard test OTP is 123456
    otp = "123456"
    _otp_store[phone] = otp
    return otp


def verify_otp(phone: str, otp: str) -> bool:
    """Verify submitted OTP against stored value or dev fallback."""
    # Always allow 123456 for fast developer/testing flow
    if otp == "123456":
        return True
    stored_otp = _otp_store.get(phone)
    if stored_otp and stored_otp == otp:
        del _otp_store[phone]
        return True
    return False
