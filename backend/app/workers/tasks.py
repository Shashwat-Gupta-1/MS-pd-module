import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.pd_session import PDSession
from app.models.officer import Officer
from app.agents.pd_workflow_graph import pd_graph, persist_batch_results, PDWorkflowState

logger = logging.getLogger(__name__)


@celery_app.task
def transcribe_session_audio(session_id: str) -> str:
    """Agent 1 STT task: runs faster-whisper transcription & speaker diarization on a PD session."""
    from app.agents.speech_to_text import run_stt
    return run_stt(session_id)


def transcribe_audio_stub(session_id: str, audio_chunk_bytes: bytes, chunk_sequence: int) -> Dict[str, Any]:
    """
    Speech-to-Text handler for live incremental audio slices.
    Backed by Agent 1 transcribe_chunk_bytes pipeline.
    """
    from app.agents.speech_to_text import transcribe_chunk_bytes
    try:
        offset = float(chunk_sequence * 15.0)
        segments = transcribe_chunk_bytes(
            audio_chunk_bytes,
            offset_sec=offset,
            session_id=session_id,
            chunk_sequence=chunk_sequence
        )
        return {"status": "transcribed", "session_id": session_id, "segments": segments}
    except Exception as e:
        logger.warning(f"transcribe_audio_stub error: {e}")
        return {"status": "failed", "session_id": session_id, "segments": []}


@celery_app.task
def extract_photo_vision_task(photo_id: str, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Agent 3 Celery Task: Executes Gemini Vision extraction, EXIF inspection,
    perceptual hash (pHash) duplicate detection, and application asset aggregation in background.
    """
    from app.agents.vision_extraction import process_and_save_photo_extraction
    import app.core.database as db_mod

    should_close_db = False
    if db is None:
        db = db_mod.SessionLocal()
        should_close_db = True
    try:
        result = process_and_save_photo_extraction(photo_id, db)
        return {"status": "success", "photo_id": photo_id, "result": result}
    except Exception as e:
        logger.error(f"Error in extract_photo_vision_task for photo {photo_id}: {e}")
        return {"status": "failed", "photo_id": photo_id, "error": str(e)}
    finally:
        if should_close_db:
            db.close()


@celery_app.task
def extract_photo_stub(photo_id: str, photo_url: str = "", category: str = "", lat: float = 0.0, lng: float = 0.0) -> Dict[str, Any]:
    """
    Contract wrapper for Vision Extraction:
    Dispatches extract_photo_vision_task and returns structured extraction summary.
    """
    return extract_photo_vision_task(photo_id)


@celery_app.task
def process_transcript_batch(
    session_id: str,
    audio_chunk_bytes: Optional[bytes] = None,
    chunk_sequence: int = 0,
    transcript_segments: Optional[List[Dict[str, Any]]] = None,
    db: Optional[Session] = None
) -> List[Dict[str, Any]]:
    """
    Orchestration task for live transcript batches:
    1. Transcribes live audio chunk using STT (or uses direct segments if provided).
    2. Retrieves current state checkpoint for session_id.
    3. Runs the 7-node LangGraph pipeline.
    4. Persists batch results to Postgres / SQLite and writes audit log.
    5. Returns active follow-up questions for live display.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True
    try:
        # 1. Fetch session details for initialization
        session = db.query(PDSession).filter(PDSession.id == session_id).first()
        if not session:
            logger.error(f"PD Session {session_id} not found")
            return []

        # 2. Resolve transcript segments
        print(f"\n==================== [MODE 1: LIVE AUDIO CHUNK #{chunk_sequence}] ====================", flush=True)
        segments = transcript_segments
        if segments is None and audio_chunk_bytes is not None:
            print(f"📦 [INGESTION] Received live audio slice: {len(audio_chunk_bytes)} bytes | Session ID: {session_id}", flush=True)
            print(f"🎙️ [AGENT 1 STT] Sending {len(audio_chunk_bytes)} bytes to STT pipeline...", flush=True)
            stt_result = transcribe_audio_stub(session_id, audio_chunk_bytes, chunk_sequence)
            segments = stt_result.get("segments", [])
            print(f"✅ [AGENT 1 OUTPUT] Whisper transcribed {len(segments)} segment(s):", flush=True)
            for s in segments:
                print(f"   ↳ [{s.get('speaker', 'unknown').upper()}] ({s.get('start', 0.0):.1f}s - {s.get('end', 0.0):.1f}s, conf={s.get('confidence', 1.0)*100:.1f}%): \"{s.get('text', '')}\"", flush=True)
        elif segments is None:
            segments = []

        # 3. Persist live segments incrementally to PostgreSQL
        if segments:
            from app.models.transcript_segment import TranscriptSegment
            from sqlalchemy import func
            last_seq = db.query(func.max(TranscriptSegment.seq)).filter_by(pd_session_id=session_id).scalar()
            base_seq = (last_seq + 1) if last_seq is not None else 0
            for i, seg in enumerate(segments):
                db.add(TranscriptSegment(
                    pd_session_id=session_id,
                    seq=base_seq + i,
                    start_time=float(seg.get("start", seg.get("start_time", 0.0))),
                    end_time=float(seg.get("end", seg.get("end_time", 0.0))),
                    speaker=str(seg.get("speaker", "borrower")),
                    text=str(seg.get("text", "")),
                    confidence=float(seg.get("confidence", 1.0)),
                    low_confidence=bool(seg.get("low_confidence", False))
                ))
            db.flush()
            all_segs = db.query(TranscriptSegment).filter_by(pd_session_id=session_id).order_by(TranscriptSegment.seq).all()
            session.transcript_raw = "\n".join(f"[{s.speaker.upper()}] {s.text}" for s in all_segs)
            db.commit()

        app = session.application
        applicant = app.applicant if app else None
        officer = db.query(Officer).filter(Officer.id == session.officer_id).first()

        emp_val = applicant.employment_type if applicant else None
        employment_type = emp_val.value if hasattr(emp_val, "value") else str(emp_val or "SELF_EMPLOYED")
        sub_val = applicant.sub_profile if applicant else None
        sub_profile = str(sub_val.value if hasattr(sub_val, "value") else (sub_val or "RETAIL"))

        officer_info = {
            "id": str(session.officer_id),
            "name": officer.name if officer else "Field Officer",
            "phone": officer.phone if officer else "9876543210",
            "branch": officer.branch if officer else "Jaipur Central",
            "role": officer.role if officer else "officer"
        }
        customer_info = {
            "id": str(applicant.id) if applicant else "N/A",
            "name": applicant.name if applicant else "Borrower",
            "phone": applicant.phone if applicant else "N/A",
            "pan": applicant.pan if applicant else "N/A",
            "employment_type": employment_type,
            "sub_profile": sub_profile
        }
        application_info = {
            "id": str(app.id) if app else "APP-2026-9823",
            "product_type": app.product_type if app else "secured_business_loan",
            "requested_amount": float(app.requested_amount) if app and app.requested_amount else 500000.0,
            "tenure": int(app.tenure) if app and app.tenure else 24,
            "status": app.status.value if hasattr(app.status, "value") else str(app.status) if app else "INTAKE"
        }

        # Audit log the Whisper transcription chunk
        from app.core.audit_logger import audit_logger
        audit_logger.log_whisper_chunk(
            session_id=session_id,
            chunk_sequence=chunk_sequence,
            audio_bytes_length=len(audio_chunk_bytes) if audio_chunk_bytes else 0,
            offset_sec=float(chunk_sequence * 15.0),
            segments=segments,
            officer_info=officer_info,
            customer_info=customer_info
        )

        rag_req = {}
        try:
            from app.rag.retrieval import get_profession_profile
            profile = get_profession_profile(sub_profile, db)
            if profile:
                rag_req = {
                    "sub_profile": profile.sub_profile,
                    "display_name": profile.display_name,
                    "benchmark_margins_json": profile.benchmark_margins_json,
                    "required_info_checklist_json": profile.required_info_checklist_json,
                    "red_flags_json": profile.red_flags_json
                }
        except Exception as e:
            logger.warning(f"Could not load RAG profile: {e}")

        if not rag_req:
            rag_req = {
                "sub_profile": sub_profile,
                "required_info_checklist_json": [
                    "monthly_turnover", "net_margin_pct", "supplier_payment_terms", "credit_ledger_recovery_cycle"
                ],
                "red_flags_json": []
            }

        # Resolve dynamic frontend questionnaire specific to this borrower's employment and business category
        dynamic_qs = []
        try:
            from app.models.question_bank import QuestionBank
            emp_clean = employment_type.lower()
            raw_cat = (getattr(applicant, "business_category", None) or getattr(applicant, "employer_type", None) or sub_profile or "").lower().replace(" ", "_")
            if raw_cat in ("govt", "government"):
                raw_cat = "salaried_govt"
            elif raw_cat in ("private", "corporate"):
                raw_cat = "salaried_private"

            t1 = db.query(QuestionBank).filter(QuestionBank.tier == 1).order_by(QuestionBank.id).all()
            t2 = db.query(QuestionBank).filter(QuestionBank.tier == 2, QuestionBank.employment_type == emp_clean).order_by(QuestionBank.id).all()
            t3 = db.query(QuestionBank).filter(QuestionBank.tier == 3, QuestionBank.business_category == raw_cat).order_by(QuestionBank.id).all()

            for q in (t1 + t2 + t3):
                dynamic_qs.append({
                    "id": q.id,
                    "tier": q.tier,
                    "field_name": q.field_name,
                    "question_text": q.question_text,
                    "data_type": q.data_type,
                    "is_mandatory": q.is_mandatory,
                    "employment_type": q.employment_type,
                    "business_category": q.business_category
                })
        except Exception as q_err:
            logger.warning(f"Failed to fetch dynamic questionnaire in tasks: {q_err}")

        config = {"configurable": {"thread_id": session_id}}
        existing_checkpoint = pd_graph.get_state(config)

        if existing_checkpoint and existing_checkpoint.values:
            curr_state = existing_checkpoint.values
            update_data = {
                "current_batch": segments,
                "batch_index": chunk_sequence,
                "dynamic_questionnaire": curr_state.get("dynamic_questionnaire") or dynamic_qs
            }
        else:
            update_data: PDWorkflowState = {
                "session_id": session_id,
                "application_id": str(app.id) if app else "",
                "employment_type": employment_type,
                "sub_profile": sub_profile,
                "rag_requirements": rag_req,
                "dynamic_questionnaire": dynamic_qs,
                "transcript_history": [],
                "current_batch": segments,
                "batch_index": chunk_sequence,
                "extracted_fields": {},
                "active_followup_questions": [],
                "resolved_followup_questions": [],
                "round_number": chunk_sequence,
                "officer_uptake_count": 0,
                "officer_proactive_bonus_points": 0,
                "customer_contradiction_count": 0,
                "detected_contradictions": [],
                "gaps_remaining": True,
                "is_session_active": True
            }

        # Terminal logging of exact inputs entering LangGraph
        prev_history = existing_checkpoint.values.get("transcript_history", []) if (existing_checkpoint and existing_checkpoint.values) else []
        prev_fields = existing_checkpoint.values.get("extracted_fields", {}) if (existing_checkpoint and existing_checkpoint.values) else {}
        prev_active_qs = existing_checkpoint.values.get("active_followup_questions", []) if (existing_checkpoint and existing_checkpoint.values) else []
        print(f"\n🧠 [LANGGRAPH NODE INPUT] Invoking 7-Node Graph for Batch #{chunk_sequence}:", flush=True)
        print(f"   • Current Batch Input Segments ({len(segments)}):", flush=True)
        for s in segments:
            print(f"       [{s.get('speaker', 'unknown').upper()}]: \"{s.get('text', '')}\"", flush=True)
        print(f"   • Profile: {customer_info['name']} | {customer_info['employment_type']} / {customer_info['sub_profile']}", flush=True)
        print(f"   • Prior Transcript Turns in History: {len(prev_history)}", flush=True)
        print(f"   • Currently Extracted Fields ({len(prev_fields)}): {list(prev_fields.keys())}", flush=True)
        print(f"   • Active Follow-up Queue ({len(prev_active_qs)}): {[q.get('question_text', '')[:45] + '...' for q in prev_active_qs]}", flush=True)
        print(f"▶️ [LANGGRAPH RUNNING] Executing nodes sequentially...", flush=True)

        # 3. Invoke graph
        result_state = pd_graph.invoke(update_data, config=config)

        print(f"🏁 [LANGGRAPH BATCH COMPLETE] Batch #{chunk_sequence} executed successfully.", flush=True)
        print(f"   • Total Turns in History: {len(result_state.get('transcript_history', []))}", flush=True)
        print(f"   • Total Extracted Fields: {len(result_state.get('extracted_fields', {}))}", flush=True)
        print(f"   • Consistency Flags: {len(result_state.get('detected_contradictions', []))}", flush=True)
        print(f"   • Active Follow-up Suggestions on Screen: {len(result_state.get('active_followup_questions', []))}", flush=True)
        print(f"=========================================================================\n", flush=True)

        # 4. Audit log LangGraph 7-node pipeline run
        audit_logger.log_langgraph_batch_execution(
            session_id=session_id,
            chunk_sequence=chunk_sequence,
            officer_info=officer_info,
            customer_info=customer_info,
            application_info=application_info,
            segments=segments,
            result_state=result_state
        )

        # 5. Persist to DB and local audit file
        active_qs = persist_batch_results(result_state, db)
        return active_qs
    finally:
        if should_close_db:
            db.close()

