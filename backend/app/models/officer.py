import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import synonym
from app.core.database import Base


class Officer(Base):
    __tablename__ = "officers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    phone_number = synonym("phone")
    role = Column(String(20), nullable=False, default="officer")  # officer | underwriter | admin
    branch = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __init__(self, **kwargs):
        if "phone_number" in kwargs and "phone" not in kwargs:
            kwargs["phone"] = kwargs.pop("phone_number")
        super().__init__(**kwargs)

