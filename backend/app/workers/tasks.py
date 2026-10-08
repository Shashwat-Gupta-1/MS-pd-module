"""Celery task definitions: transcribe_audio, run_classify_rag (called once per gap-question round), extract_photo, score_officer, check_customer_consistency, assemble_report."""
from app.agents.llm_client import get_llm
from app.agents.speech_to_text import run_stt
from app.workers.celery_app import celery_app


@celery_app.task(name="pd.transcribe_session", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def transcribe_session(session_id: str) -> str:
    """Agent 1. Returns the session_id so the next task in a chain receives it."""
    return run_stt(session_id, get_llm())


@celery_app.task(name="pd.extract_photo", autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def extract_photo(photo_id: str, photo_path: str, category: str, application_id: str) -> dict:
    """Agent 3. Asynchronous vision extraction for background photo processing."""
    from app.agents.vision_extraction import extract_photo_vision
    return extract_photo_vision(photo_path=photo_path, category=category)



# Called from api/routes/pd_sessions.py once the master audio file exists:
#     from app.workers.tasks import transcribe_session
#     transcribe_session.delay(session_id)
