import enum
import uuid
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class ApplicationStatusEnum(str, enum.Enum):
    INTAKE = "INTAKE"
    LEAD_CREATED = "INTAKE"
    PD_IN_PROGRESS = "PD_IN_PROGRESS"
    PD_COMPLETE = "PD_COMPLETE"
    UNDERWRITING_REVIEW = "UNDERWRITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Application(Base):
    __tablename__ = "applications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    applicant_id = Column(String(36), ForeignKey("applicants.id"), nullable=False, index=True)
    product_type = Column(String(50), nullable=False)
    requested_amount = Column(Float, nullable=False)
    tenure = Column(Integer, nullable=False)  # in months
    rate = Column(Float, nullable=False)  # annual interest rate %
    status = Column(String(30), nullable=False, default="INTAKE")  # INTAKE | PD_IN_PROGRESS | PD_COMPLETE
    geo_confirmation_status = Column(String(30), nullable=False, default="insufficient_photos")  # confirmed | flagged | insufficient_photos
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __init__(self, **kwargs):
        if "loan_type" in kwargs and "product_type" not in kwargs:
            kwargs["product_type"] = kwargs.pop("loan_type")
        if "tenure_months" in kwargs and "tenure" not in kwargs:
            kwargs["tenure"] = kwargs.pop("tenure_months")
        if "interest_rate" in kwargs and "rate" not in kwargs:
            kwargs["rate"] = kwargs.pop("interest_rate")
        if "case_number" in kwargs:
            kwargs.pop("case_number")
        if "tenure" not in kwargs or kwargs["tenure"] is None:
            kwargs["tenure"] = 60
        if "rate" not in kwargs or kwargs["rate"] is None:
            kwargs["rate"] = 12.0
        super().__init__(**kwargs)

    applicant = relationship("Applicant", backref="applications")

    @property
    def case_number(self) -> str:
        return f"APP-{self.id[:8].upper()}"

    @case_number.setter
    def case_number(self, value: str):
        pass

    @property
    def loan_type(self) -> str:
        return self.product_type

    @loan_type.setter
    def loan_type(self, value: str):
        self.product_type = value

    @property
    def tenure_months(self) -> int:
        return self.tenure

    @tenure_months.setter
    def tenure_months(self, value: int):
        self.tenure = value

    @property
    def interest_rate(self) -> float:
        return self.rate

    @interest_rate.setter
    def interest_rate(self, value: float):
        self.rate = value

    @property
    def collateral_value(self) -> float:
        return 0.0

