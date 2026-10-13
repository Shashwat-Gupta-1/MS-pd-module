import enum
import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import synonym
from app.core.database import Base


class EmploymentTypeEnum(str, enum.Enum):
    SELF_EMPLOYED = "self_employed"
    SALARIED = "salaried"


class Applicant(Base):
    __tablename__ = "applicants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    full_name = synonym("name")
    phone = Column(String(20), unique=True, nullable=False, index=True)
    phone_number = synonym("phone")
    pan = Column(String(10), nullable=True, index=True)
    pan_number = synonym("pan")
    aadhaar_number = Column(String(12), nullable=True)
    employment_type = Column(String(30), nullable=False)  # self_employed | salaried
    business_category = Column(String(100), nullable=True)
    employer_type = Column(String(100), nullable=True)  # for salaried applicants
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __init__(self, **kwargs):
        if "phone_number" in kwargs and "phone" not in kwargs:
            kwargs["phone"] = kwargs.pop("phone_number")
        if "full_name" in kwargs and "name" not in kwargs:
            kwargs["name"] = kwargs.pop("full_name")
        if "pan_number" in kwargs and "pan" not in kwargs:
            kwargs["pan"] = kwargs.pop("pan_number")
        if "sub_profile" in kwargs and "business_category" not in kwargs:
            kwargs["business_category"] = kwargs.pop("sub_profile")
        super().__init__(**kwargs)

    @property
    def sub_profile(self) -> str:
        return (self.business_category or self.employer_type or "RETAIL").upper()

    @sub_profile.setter
    def sub_profile(self, value: str):
        self.business_category = value

    @property
    def declared_monthly_income(self) -> float:
        return 50000.0

