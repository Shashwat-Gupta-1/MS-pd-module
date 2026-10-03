"""SQLAlchemy engine, session factory, and Base declarative class. All models import Base from here."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings


class Base(DeclarativeBase):
    """All models inherit from this. Alembic's env.py should use Base.metadata as target_metadata."""
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI dependency (use it from api/deps.py): one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()