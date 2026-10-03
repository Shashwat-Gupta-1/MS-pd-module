"""FastAPI router for Personal Discussion (PD) sessions.

Endpoints:
- POST /pd-sessions (start session, captures consent)
- POST /pd-sessions/{id}/audio (upload recording and transcribe via Agent 1)
- GET /pd-sessions/{id} (retrieve session transcript and status)
"""
import os
import shutil
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.agents.llm_client import get_llm
from app.agents.speech_to_text import decode_to_wav, probe_duration, tag_speakers, transcribe_wav
from app.core.config import settings
from app.utils.stt_utils import dedupe_segments, segment_confidence, split_segments_by_word_gaps

router = APIRouter(prefix="/pd-sessions", tags=["Personal Discussion Sessions"])


@router.post("/{session_id}/audio")
async def upload_session_audio(
    session_id: str,
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    consent_captured: Optional[bool] = Form(True),
):
    """Processes audio for a PD Session through Agent 1 pipeline."""
    temp_dir = tempfile.mkdtemp(prefix=f"pd_{session_id}_")
    try:
        input_extension = os.path.splitext(file.filename or "recording.webm")[1] or ".webm"
        raw_audio_path = os.path.join(temp_dir, f"raw{input_extension}")
        wav_path = os.path.join(temp_dir, "master_16k.wav")

        with open(raw_audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        decode_to_wav(raw_audio_path, wav_path)
        duration = probe_duration(wav_path)

        raw_segs, detected_lang = transcribe_wav(wav_path, language=language)
        effective_lang = language or detected_lang

        segs = dedupe_segments(raw_segs)
        segs = split_segments_by_word_gaps(segs, min_gap_sec=0.7)

        llm = get_llm()
        segs, speakers = tag_speakers(llm, segs)

        processed_segments = []
        transcript_lines = []

        for seq, (seg, spk) in enumerate(zip(segs, speakers)):
            conf, min_w = segment_confidence(seg.get("words", []), seg.get("avg_logprob"))
            conf_val = float(conf) if conf is not None else 0.0
            min_w_val = float(min_w) if min_w is not None else None
            is_low_conf = bool(conf_val < settings.low_conf_threshold)

            seg_data = {
                "seq": int(seq),
                "speaker": str(spk),
                "text": str(seg["text"]),
                "start_time": round(float(seg["start"]), 2),
                "end_time": round(float(seg["end"]), 2),
                "confidence": round(conf_val, 4),
                "min_word_conf": round(min_w_val, 4) if min_w_val is not None else None,
                "low_confidence": is_low_conf,
            }
            processed_segments.append(seg_data)
            transcript_lines.append(f"[{spk}] {seg['text']}")

        transcript_raw = "\n".join(transcript_lines)

        # ---- Persist to Database Session-wise ----
        try:
            from app.core.database import SessionLocal
            from app.models.application import Application
            from app.models.pd_session import PDSession
            from app.models.transcript_segment import TranscriptSegment

            with SessionLocal() as db:
                # Ensure application record exists for foreign key
                app_obj = db.get(Application, session_id)
                if not app_obj:
                    app_obj = Application(
                        id=session_id,
                        borrower_name="Ramesh Kumar",
                        product_type="Micro Enterprise Loan",
                        status="PD_IN_PROGRESS",
                    )
                    db.add(app_obj)
                    db.flush()

                session_obj = db.get(PDSession, session_id)
                if not session_obj:
                    session_obj = PDSession(
                        id=session_id,
                        application_id=session_id,
                        channel="ground",
                        consent_captured=bool(consent_captured),
                    )
                    db.add(session_obj)

                session_obj.transcript_raw = transcript_raw
                session_obj.duration_sec = float(duration)
                session_obj.language = str(effective_lang)
                session_obj.status = "transcribed"

                db.query(TranscriptSegment).filter_by(pd_session_id=session_id).delete()
                for item in processed_segments:
                    db.add(TranscriptSegment(
                        pd_session_id=session_id,
                        seq=item["seq"],
                        speaker=item["speaker"],
                        text=item["text"],
                        start_time=item["start_time"],
                        end_time=item["end_time"],
                        confidence=item["confidence"],
                        min_word_conf=item.get("min_word_conf"),
                        low_confidence=item["low_confidence"],
                    ))
                db.commit()
        except Exception as db_err:
            import logging
            logging.getLogger(__name__).warning("DB persistence skipped/failed: %s", db_err)

        return JSONResponse({
            "status": "success",
            "session_id": str(session_id),
            "duration_sec": round(float(duration), 2),
            "language": str(effective_lang),
            "consent_captured": bool(consent_captured),
            "total_segments": len(processed_segments),
            "transcript_raw": transcript_raw,
            "segments": processed_segments,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process session audio: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
