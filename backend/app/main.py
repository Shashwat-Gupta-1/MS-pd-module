"""FastAPI application entrypoint for MSFincap PD Module.

Registers CORS middleware, routers, and the speech-to-text (Agent 1) pipeline endpoints.
"""
import logging
import os
import shutil
import sys
import tempfile
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Setup unified logging (Console + backend.log)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("backend.log", encoding="utf-8", mode="a")
    ],
    force=True,
)
log = logging.getLogger("msfincap.stt")

from app.agents.llm_client import get_llm
from app.agents.speech_to_text import decode_to_wav, probe_duration, tag_speakers, transcribe_wav
from app.core.config import settings
from app.utils.stt_utils import (
    dedupe_segments,
    filter_hallucinated_segments,
    merge_consecutive_speaker_segments,
    segment_confidence,
    split_segments_by_word_gaps,
)

app = FastAPI(
    title="MSFincap PD Module API",
    description="Backend API for Personal Discussion AI Module",
    version="1.0.0",
)

# Import all models to ensure they are registered with Base metadata
from app.models import application, pd_session, transcript_segment, occupation_config, photo_category_config, ground_pd_photo, photo_extraction, asset_valuation, business_estimate
from app.core.database import Base, engine

try:
    Base.metadata.create_all(bind=engine)
except Exception as db_init_err:
    log.warning("Table auto-creation skipped: %s", db_init_err)

from app.api.routes.pd_sessions import router as pd_sessions_router
from app.api.routes.ground_pd import router as ground_pd_router
from app.api.routes.applications import router as applications_router

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

# Mount uploads directory for static photo viewing
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(pd_sessions_router, prefix="/api")
app.include_router(ground_pd_router, prefix="/api")
app.include_router(applications_router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "MSFincap PD Module API",
        "whisper_model": settings.whisper_model,
        "whisper_device": settings.whisper_device,
        "gemini_model": settings.gemini_model,
    }


@app.post("/api/transcribe-audio")
async def transcribe_audio_endpoint(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    consent_captured: Optional[bool] = Form(True),
):
    """Direct Agent 1 Speech-to-Text endpoint.

    Accepts uploaded audio file (MP3, WAV, WebM, M4A, AAC, etc.),
    decodes it, runs faster-whisper with VAD & word timestamps,
    splits word gaps, tags speakers via Gemini LLM, and calculates confidence.
    """
    if not session_id:
        session_id = f"pd_{uuid.uuid4().hex[:8]}"

    log.info("=" * 60)
    log.info("▶ Starting STT request for session: %s (filename: %s)", session_id, file.filename)

    temp_dir = tempfile.mkdtemp(prefix="api_stt_")
    try:
        # 1. Save uploaded file to disk
        input_extension = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
        raw_audio_path = os.path.join(temp_dir, f"raw_audio{input_extension}")
        wav_path = os.path.join(temp_dir, "master_16k.wav")

        with open(raw_audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Decode to 16kHz mono WAV using ffmpeg
        decode_to_wav(raw_audio_path, wav_path)
        duration = probe_duration(wav_path)
        log.info("[Step 1/5] Decoded to 16kHz mono WAV. Audio duration: %.2f seconds", duration)

        # 3. Transcribe using STT (Sarvam AI / Groq / Faster-Whisper)
        log.info("[Step 2/5] Transcribing audio with multi-tier STT engine...")
        raw_segs, detected_lang = transcribe_wav(wav_path, language=language)
        effective_lang = language or detected_lang
        log.info("[Step 2/5] STT engine produced %d raw segments (Detected language: %s)", len(raw_segs), detected_lang)

        # 4. Clean & split segments by silence word gaps
        segs = dedupe_segments(raw_segs)
        segs = filter_hallucinated_segments(segs)
        segs = split_segments_by_word_gaps(segs, min_gap_sec=0.5)
        segs = filter_hallucinated_segments(segs)
        log.info("[Step 3/5] Deduplication & word gap splitting produced %d segments", len(segs))

        # 5. Speaker tagging & turn splitting via Gemini LLM
        log.info("[Step 4/5] Sending segments to Gemini LLM for speaker tagging & phonetic cleanup...")
        llm = get_llm()
        segs, speakers = tag_speakers(llm, segs)
        segs, speakers = merge_consecutive_speaker_segments(segs, speakers, max_gap_sec=1.5)
        log.info("[Step 4/5] Gemini speaker tagging & turn merging finished successfully (%d final turns).", len(segs))

        # 6. Build structured response segments with confidence metrics
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
            log.info("   ↳ [%s] (%.1fs -> %.1fs) %s (conf: %.1f%%)", spk.upper(), seg['start'], seg['end'], seg['text'], conf_val * 100)

        transcript_raw = "\n".join(transcript_lines)
        log.info("[Step 5/5] Persisting %d transcript segments to database...", len(processed_segments))

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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
