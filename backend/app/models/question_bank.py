from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import synonym
from app.core.database import Base


class QuestionBank(Base):
    __tablename__ = "question_bank"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tier = Column(Integer, nullable=False, index=True)  # 1 | 2 | 3
    employment_type = Column(String(50), nullable=True, index=True)  # self_employed | salaried | all
    category = synonym("employment_type")
    business_category = Column(String(100), nullable=True, index=True)  # retail, manufacturing, services, etc.
    sub_profile = synonym("business_category")
    question_text = Column(String(500), nullable=False)
    field_name = Column(String(100), nullable=False, index=True)
    question_code = synonym("field_name")
    data_type = Column(String(50), nullable=False, default="text")  # text | number | boolean | select
    is_mandatory = Column(Boolean, nullable=False, default=True)
