"""Agent 1: runs faster-whisper on a pd_session recording, writes transcript_raw + transcript_segments with confidence scores.

Also fills `speaker` on every segment (officer / borrower / unknown) so later agents can group Q&A turns directly.

Flow: master audio -> 16 kHz mono WAV -> (split at silences if very long) -> faster-whisper with VAD and
word timestamps -> de-duplicate overlaps -> speaker labels -> save.

Sections in this file:
  1. Audio helpers (ffmpeg)
  2. Transcription (faster-whisper)
  3. Speaker labelling (LLM, heuristic fallback)
  4. run_stt  <- entry point called by workers/tasks.py
"""
import json
import logging
import os
import shutil
import subprocess
import tempfile

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.pd_session import PDSession
from app.models.transcript_segment import TranscriptSegment
from app.utils.stt_utils import (dedupe_segments, heuristic_tag, parse_silences, plan_pieces,
                                 segment_confidence, split_segments_by_word_gaps)
from app.agents.llm_client import get_llm


log = logging.getLogger(__name__)
_MODEL = None

# Patch PyAV 14+ compatibility where metadata_errors was removed from av.open
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return _orig_av_open(*args, **kwargs)

    av.open = _safe_av_open
except Exception:
    pass


# ====================== 1. Audio helpers (ffmpeg must be installed) ======================


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def local_audio_path(uri: str) -> str:
    """Plug your file-storage layer in here. Local paths and file:// URIs are supported out of the box."""
    if uri.startswith("file://"):
        return uri[7:]
    if "://" in uri:
        raise NotImplementedError("Download remote audio to a temp file here (e.g. from S3/MinIO).")
    return uri


def decode_to_wav(src: str, dst: str) -> None:
    """Whisper resamples to 16 kHz mono anyway, so decoding to it loses nothing. The stored master is untouched."""
    _run([
        "ffmpeg", "-y",
        "-err_detect", "ignore_err",
        "-fflags", "+genpts+discardcorrupt",
        "-i", src,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", dst
    ])


def probe_duration(path: str) -> float:
    out = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path]).stdout
    return float(json.loads(out)["format"]["duration"])


def detect_silences(wav: str) -> list[tuple[float, float]]:
    p = subprocess.run(
        ["ffmpeg", "-i", wav, "-af", "silencedetect=noise=-35dB:d=0.7", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return parse_silences(p.stderr)


def cut_piece(wav: str, start: float, end: float, out: str) -> None:
    _run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", wav, "-c", "copy", out])


# ====================== 2. Transcription (faster-whisper) ======================
_CURRENT_MODEL_NAME = None


def _get_model(model_name: str | None = None):
    global _MODEL, _CURRENT_MODEL_NAME
    req_model = model_name or settings.whisper_model
    if _MODEL is None or _CURRENT_MODEL_NAME != req_model:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(req_model, device=settings.whisper_device,
                              compute_type=settings.whisper_compute_type)
        _CURRENT_MODEL_NAME = req_model
    return _MODEL


def transcribe_wav(path: str, language: str | None, prompt: str | None = None) -> tuple[list[dict], str | None]:
    it, info = _get_model().transcribe(
        path,
        language=language,                       # None = auto-detect; pass "hi" if you know it
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        word_timestamps=True,
        beam_size=5,
        initial_prompt=prompt or settings.whisper_initial_prompt,
        condition_on_previous_text=False,        # avoids repetition loops on long audio
    )
    out = []
    for seg in it:
        text = seg.text.strip()
        if not text:
            continue
        words = [{"w": w.word, "start": w.start, "end": w.end, "p": w.probability} for w in (seg.words or [])]
        out.append({"start": seg.start, "end": seg.end, "text": text,
                    "avg_logprob": seg.avg_logprob, "no_speech_prob": seg.no_speech_prob, "words": words})
    return out, info.language


# ====================== 3. Speaker labelling ======================
SPEAKER_LABELS = {"officer", "borrower", "unknown"}
SPEAKER_BATCH = 50
SPEAKER_CONTEXT = 6

SPEAKER_SYSTEM_PROMPT = (
    "You are an expert dialogue speaker classifier and phonetic transcript normalizer for loan-officer field interviews in India (supporting any regional language, Hindi, Hinglish, or English).\n\n"
    "There are two speakers:\n"
    "- 'officer': The loan verification officer asking questions, guiding the interview, verifying documents/business.\n"
    "- 'borrower': The applicant answering questions, sharing details about themselves, business, family, or income.\n\n"
    "TASK:\n"
    "1. Classify the speaker ('officer' or 'borrower') for every segment_index.\n"
    "2. In 'corrected_text', fix phonetic speech-to-text mistranscriptions and spelling distortions in Romanized or conversational speech using surrounding grammatical and semantic context.\n\n"
    "CRITICAL RULES & SAFETY BOUNDARIES:\n"
    "1. You MUST NOT invent, add, delete, or rephrase sentences, questions, or dialogue.\n"
    "2. You MUST keep the exact conversational meaning and sentence structure intact.\n"
    "3. Only fix words that are clear phonetic speech-to-text recognition errors in their context. If a word is a valid proper noun, place name, person's name, or legitimate term, leave it untouched.\n"
    "4. Return JSON only with a 'labels' list containing every segment_index with its 'speaker' and 'corrected_text':\n"
    '{"labels": [{"segment_index": <int>, "speaker": "officer" | "borrower", "corrected_text": "<string>"}]}'
)


def tag_speakers(llm=None, segments: list[dict] = None) -> tuple[list[dict], list[str]]:
    """Identifies dialogue turns, splits mixed Q&A turns, and polishes transcript text.

    Returns (refined_segments, speaker_labels).
    """
    if not segments:
        return [], []
    if llm is None:
        llm = get_llm(provider="gemini", task="diarization")

    try:
        model_name = getattr(llm, "model", None) or "multi-model-pool"
        log.info(f"[Agent 1 Diarization] Tagging {len(segments)} segments & normalizing dialogue with Gemini ({model_name})...")
        print(f"[Agent 1 Diarization] Tagging {len(segments)} segments & normalizing dialogue with Gemini ({model_name})...", flush=True)

        user_payload = json.dumps({
            "segments": [{"segment_index": i, "text": s["text"]} for i, s in enumerate(segments)]
        }, ensure_ascii=False)

        res = llm.complete_json(SPEAKER_SYSTEM_PROMPT, user_payload)
        turns = res.get("labels") or res.get("turns", [])

        if not turns:
            raise ValueError("No dialogue turns returned from LLM")

        turns_by_idx: dict[int, list[dict]] = {}
        for turn in turns:
            idx = turn.get("segment_index", 0)
            turns_by_idx.setdefault(idx, []).append(turn)

        refined_segments: list[dict] = []
        speaker_labels: list[str] = []

        for idx, sub_turns in turns_by_idx.items():
            orig_seg = segments[idx] if 0 <= idx < len(segments) else segments[0]
            total_duration = max(0.1, orig_seg["end"] - orig_seg["start"])
            total_chars = sum(len((t.get("corrected_text") or t.get("text", "")).strip()) for t in sub_turns) or 1

            cur_start = orig_seg["start"]
            for i, turn in enumerate(sub_turns):
                spk = turn.get("speaker", "borrower")
                if spk not in SPEAKER_LABELS:
                    spk = "borrower"
                turn_text = (turn.get("corrected_text") or turn.get("text") or orig_seg["text"]).strip()
                char_ratio = len(turn_text) / total_chars
                turn_duration = total_duration * char_ratio
                cur_end = orig_seg["end"] if i == len(sub_turns) - 1 else round(cur_start + turn_duration, 2)

                new_seg = {
                    "start": cur_start,
                    "end": cur_end,
                    "text": turn_text,
                    "words": orig_seg.get("words", []),
                    "avg_logprob": orig_seg.get("avg_logprob"),
                    "no_speech_prob": orig_seg.get("no_speech_prob"),
                }
                refined_segments.append(new_seg)
                speaker_labels.append(spk)
                cur_start = cur_end

        return refined_segments, speaker_labels

    except Exception as e:
        log.warning("Smart speaker dialogue parser failed: %s (using heuristic fallback)", e)
        fallback = heuristic_tag(segments)
        return segments, fallback


def transcribe_groq_whisper(
    wav_path: str,
    language: str | None = None,
    prompt: str | None = None
) -> tuple[list[dict], str | None]:
    """Transcribes audio using Groq's high-speed whisper-large-v3-turbo model with round-robin key pool rotation."""
    from app.agents.llm_client import complete_audio_transcription
    model = getattr(settings, "GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

    with open(wav_path, "rb") as f:
        audio_bytes = f.read()

    res = complete_audio_transcription(
        audio_bytes=audio_bytes,
        filename="chunk.wav",
        model=model,
        prompt=(prompt or settings.whisper_initial_prompt)[:880],
        response_format="verbose_json",
        language=language
    )

    out = []
    raw_segments = getattr(res, "segments", None)
    if raw_segments is None and isinstance(res, dict):
        raw_segments = res.get("segments", [])

    if raw_segments:
        for seg in raw_segments:
            seg_dict = seg if isinstance(seg, dict) else seg.model_dump() if hasattr(seg, "model_dump") else seg.__dict__
            text = (seg_dict.get("text") or "").strip()
            if not text:
                continue
            out.append({
                "start": float(seg_dict.get("start", 0.0)),
                "end": float(seg_dict.get("end", 0.0)),
                "text": text,
                "avg_logprob": float(seg_dict.get("avg_logprob", 0.0)),
                "no_speech_prob": float(seg_dict.get("no_speech_prob", 0.0)),
                "words": []
            })
    elif hasattr(res, "text") and res.text.strip():
        out.append({
            "start": 0.0,
            "end": probe_duration(wav_path),
            "text": res.text.strip(),
            "avg_logprob": 0.0,
            "no_speech_prob": 0.0,
            "words": []
        })

    detected_lang = getattr(res, "language", None)
    return out, detected_lang


def transcribe_chunk_bytes(
    chunk_bytes: bytes,
    language: str | None = None,
    offset_sec: float = 0.0,
    session_id: str | None = None,
    chunk_sequence: int = 0,
    llm=None,
    prompt: str | None = None
) -> list[dict]:
    """
    Directly transcribes an incremental live audio chunk (e.g. 15-30s from browser MediaRecorder)
    without needing a pre-existing stored master file.
    Returns list of segment dicts with 'start', 'end', 'speaker', 'text', 'confidence'.
    """
    if not chunk_bytes:
        return []
    if llm is None:
        llm = get_llm(provider="gemini", task="diarization")

    # Save audio copy to uploads/recordings for audit and playback
    if session_id:
        try:
            settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
            chunk_save_path = settings.RECORDINGS_DIR / f"{session_id}_batch_{chunk_sequence}.webm"
            with open(chunk_save_path, "wb") as f:
                f.write(chunk_bytes)
            log.info(f"Saved live audio chunk to {chunk_save_path} ({len(chunk_bytes)} bytes)")
        except Exception as save_err:
            log.warning(f"Could not persist chunk audio copy: {save_err}")

    tmp = tempfile.mkdtemp(prefix="stt_chunk_")
    try:
        raw_in = os.path.join(tmp, "chunk_raw.webm")
        with open(raw_in, "wb") as f:
            f.write(chunk_bytes)

        wav = os.path.join(tmp, "chunk16k.wav")
        decode_to_wav(raw_in, wav)

        # STT Engine: Whisper exclusively (Groq whisper-large-v3-turbo -> local faster-whisper fallback)
        engine = getattr(settings, "STT_ENGINE", "groq").lower()
        raw_segs = []
        detected_lang = None
        whisper_mdl = getattr(settings, "GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

        if engine == "groq":
            try:
                print(f">> [Groq LPU STT] Transcribing with {whisper_mdl}...", flush=True)
                raw_segs, detected_lang = transcribe_groq_whisper(wav, language, prompt=prompt)
            except Exception as groq_err:
                log.warning(f"Groq Whisper failed: {groq_err}. Falling back to local faster-whisper.")
                print(f"** [Groq STT Fallback] {groq_err}. Falling back to local Whisper ({settings.whisper_model})...", flush=True)
                raw_segs, detected_lang = transcribe_wav(wav, language, prompt=prompt)
        else:
            print(f">> [Whisper STT] Decoding audio with local Whisper ({settings.whisper_model})...", flush=True)
            raw_segs, detected_lang = transcribe_wav(wav, language, prompt=prompt)

        if not raw_segs:
            log.info(f"Chunk {chunk_sequence} transcribed with 0 speech segments (silence or non-speech).")
            return []

        segs = split_segments_by_word_gaps(raw_segs, min_gap_sec=0.7)
        refined_segs, speakers = tag_speakers(llm, segs)

        out: list[dict] = []
        for s, spk in zip(refined_segs, speakers):
            conf, min_w = segment_confidence(s.get("words", []), s.get("avg_logprob"))
            conf_val = float(conf) if conf is not None else 1.0
            start_val = round(float(s["start"]) + offset_sec, 2)
            end_val = round(float(s["end"]) + offset_sec, 2)
            seg_dict = {
                "start": start_val,
                "end": end_val,
                "start_time": start_val,
                "end_time": end_val,
                "speaker": str(spk),
                "text": str(s["text"]),
                "confidence": conf_val,
                "low_confidence": bool(conf_val < settings.low_conf_threshold)
            }
            out.append(seg_dict)
            msg = f">> [Whisper Live Chunk {chunk_sequence}] [{spk.upper()}] ({start_val}s-{end_val}s, conf={conf_val*100:.1f}%): \"{s['text']}\""
            log.info(msg)
            print(msg, flush=True)

        return out
    except Exception as e:
        log.warning(f"transcribe_chunk_bytes failed: {e}")
        return []
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ====================== 4. Entry point ======================
def run_stt(session_id: str, llm=None) -> str:
    """Celery entry point. Idempotent: re-running replaces earlier transcript rows. Returns session_id."""
    if llm is None:
        llm = get_llm(provider="gemini", task="diarization")

    with SessionLocal() as db:
        s = db.get(PDSession, session_id)
        if s is None:
            raise ValueError(f"pd_session {session_id} not found")
        s.status = "transcribing"
        db.commit()
        tmp = tempfile.mkdtemp(prefix="stt_")
        try:
            wav = os.path.join(tmp, "master16k.wav")
            decode_to_wav(local_audio_path(s.recording_url), wav)
            duration = probe_duration(wav)

            if duration > settings.long_audio_sec:
                pieces = plan_pieces(detect_silences(wav), duration, settings.piece_target_sec)
            else:
                pieces = [(0.0, duration)]

            all_segs: list[dict] = []
            language = s.language
            for i, (a, b) in enumerate(pieces):
                if len(pieces) == 1:
                    path, offset = wav, 0.0
                else:
                    offset = max(0.0, a - settings.piece_overlap_sec) if i > 0 else 0.0
                    path = os.path.join(tmp, f"piece_{i}.wav")
                    cut_piece(wav, offset, b, path)

                engine = getattr(settings, "STT_ENGINE", "groq").lower()
                if engine == "groq":
                    try:
                        segs, detected = transcribe_groq_whisper(path, language)
                    except Exception as groq_err:
                        log.warning(f"Groq Whisper failed on piece {i}: {groq_err}. Falling back to local.")
                        segs, detected = transcribe_wav(path, language)
                else:
                    segs, detected = transcribe_wav(path, language)

                language = language or detected
                for seg in segs:                       # shift to absolute time
                    seg["start"] += offset
                    seg["end"] += offset
                    for w in seg["words"]:
                        w["start"] += offset
                        w["end"] += offset
                all_segs.extend(segs)

            segs = dedupe_segments(all_segs)
            segs = split_segments_by_word_gaps(segs, min_gap_sec=0.7)
            segs, speakers = tag_speakers(llm, segs)

            # ---- persist (replace any earlier run) ----
            db.query(TranscriptSegment).filter_by(pd_session_id=session_id).delete()
            for seq, (seg, spk) in enumerate(zip(segs, speakers)):
                conf, min_w = segment_confidence(seg.get("words", []), seg.get("avg_logprob"))
                conf_val = float(conf) if conf is not None else 1.0
                min_w_val = float(min_w) if min_w is not None else None
                start_val = float(seg["start"])
                end_val = float(seg["end"])
                db.add(TranscriptSegment(
                    pd_session_id=session_id, seq=int(seq),
                    start_time=start_val, end_time=end_val,
                    speaker=str(spk), text=str(seg["text"]),
                    confidence=conf_val, min_word_conf=min_w_val,
                    low_confidence=bool(conf_val < settings.low_conf_threshold),
                ))
            s.transcript_raw = "\n".join(f"[{spk}] {seg['text']}" for seg, spk in zip(segs, speakers))
            
            # Clean JSON for postgres JSON column
            json_safe_segs = json.loads(json.dumps(segs, default=lambda x: float(x) if hasattr(x, "item") else str(x)))
            active_engine = getattr(settings, "STT_ENGINE", "groq").lower()
            whisper_mdl = getattr(settings, "GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
            model_id = f"groq:{whisper_mdl}" if active_engine == "groq" else f"faster-whisper:{settings.whisper_model}"
            s.raw_asr_json = {
                "model": model_id,
                "language": language,
                "pieces": [[float(p[0]), float(p[1])] for p in pieces],
                "segments": json_safe_segs
            }
            s.duration_sec = float(duration)
            s.language = language
            s.status = "transcribed"
            db.commit()
            return session_id
        except Exception:
            db.rollback()
            s = db.get(PDSession, session_id)
            s.status = "failed_stt"
            db.commit()
            raise
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

