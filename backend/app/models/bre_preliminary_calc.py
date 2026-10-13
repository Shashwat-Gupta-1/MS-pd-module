import uuid
from sqlalchemy import Column, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class BREPreliminaryCalc(Base):
    __tablename__ = "bre_preliminary_calcs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    application_id = Column(String(36), ForeignKey("applications.id"), nullable=False, index=True)
    emi_calculated = Column(Float, nullable=False)
    foir_pct = Column(Float, nullable=False)
    ltv_pct = Column(Float, nullable=True)
    ltv_status = Column(String(50), nullable=False)  # computed | not_applicable | pending_collateral_valuation
    computed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application = relationship("Application", backref="bre_calcs")
