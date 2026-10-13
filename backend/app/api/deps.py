from typing import Generator, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.officer import Officer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_officer(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Officer:
    """Validate JWT token and return the authenticated Officer."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    officer_id: str = payload.get("sub")
    if not officer_id:
        raise credentials_exception

    officer = db.query(Officer).filter(Officer.id == officer_id).first()
    if not officer:
        raise credentials_exception

    return officer


def require_role(allowed_roles: List[str]):
    """Enforce role-based access control (e.g. ['admin'], ['officer', 'underwriter'])."""
    def role_checker(current_officer: Officer = Depends(get_current_officer)) -> Officer:
        if current_officer.role not in allowed_roles and current_officer.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Requires role: {', '.join(allowed_roles)}"
            )
        return current_officer
    return role_checker
