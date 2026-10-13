import json
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.question_bank import QuestionBank
from app.schemas.question_bank import QuestionBankCreate


def get_questions_directory() -> Path:
    """Return the absolute path to the questions data directory."""
    return Path(__file__).resolve().parent.parent / "data" / "questions"


def scan_question_files() -> List[Dict[str, Any]]:
    """Scan all JSON files in backend/app/data/questions/ and return raw question dictionaries."""
    questions_dir = get_questions_directory()
    if not questions_dir.exists():
        return []

    collected_questions: List[Dict[str, Any]] = []
    for json_file in questions_dir.rglob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    collected_questions.extend(data)
        except Exception as e:
            print(f"[Warning] Failed to parse question file {json_file}: {e}")

    return collected_questions


def sync_questions_to_db(db: Session) -> Dict[str, int]:
    """Scan question files and upsert them into the PostgreSQL question_bank table."""
    raw_questions = scan_question_files()
    upserted_count = 0

    for q_data in raw_questions:
        validated = QuestionBankCreate(**q_data)
        
        # Check if question already exists by tier and field_name
        existing = db.query(QuestionBank).filter(
            QuestionBank.tier == validated.tier,
            QuestionBank.field_name == validated.field_name
        ).first()

        if existing:
            existing.question_text = validated.question_text
            existing.employment_type = validated.employment_type
            existing.business_category = validated.business_category
            existing.data_type = validated.data_type
            existing.is_mandatory = validated.is_mandatory
        else:
            new_q = QuestionBank(
                tier=validated.tier,
                employment_type=validated.employment_type,
                business_category=validated.business_category,
                question_text=validated.question_text,
                field_name=validated.field_name,
                data_type=validated.data_type,
                is_mandatory=validated.is_mandatory,
            )
            db.add(new_q)
        
        upserted_count += 1

    db.commit()
    return {"total_questions_synced": upserted_count}
