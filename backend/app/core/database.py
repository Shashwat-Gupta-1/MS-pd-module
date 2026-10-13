from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.sqlalchemy_database_url,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema_migrations(target_engine=None):
    """Idempotently adds any new model columns that may be missing in existing tables."""
    eng = target_engine or engine
    try:
        from sqlalchemy import text, inspect
        insp = inspect(eng)
        if insp.has_table("photo_extractions"):
            cols = {c["name"] for c in insp.get_columns("photo_extractions")}
            migrations = [
                ("category_matches_photo", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS category_matches_photo BOOLEAN DEFAULT TRUE"),
                ("category_mismatch_reason", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS category_mismatch_reason TEXT"),
                ("premises_type", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS premises_type VARCHAR(100)"),
                ("stock_level", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS stock_level VARCHAR(50)"),
                ("employee_count_visible", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS employee_count_visible INTEGER DEFAULT 0"),
                ("customer_activity_visible", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS customer_activity_visible VARCHAR(50)"),
                ("overall_condition", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS overall_condition VARCHAR(50)"),
                ("items", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS items JSON DEFAULT '[]'::json"),
                ("estimated_total_value_min", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS estimated_total_value_min FLOAT DEFAULT 0.0"),
                ("estimated_total_value_max", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS estimated_total_value_max FLOAT DEFAULT 0.0"),
                ("summary", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS summary TEXT"),
                ("raw_extraction", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS raw_extraction JSON"),
                ("created_at", "ALTER TABLE photo_extractions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
            ]
            with eng.begin() as conn:
                for col_name, sql in migrations:
                    if col_name not in cols:
                        try:
                            conn.execute(text(sql))
                        except Exception:
                            pass
    except Exception:
        pass

