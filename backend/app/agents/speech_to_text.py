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


log = logging.getLogger(__name__)
_MODEL = None


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
    _run(["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", dst])


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
def _get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(settings.whisper_model, device=settings.whisper_device,
                              compute_type=settings.whisper_compute_type)
    return _MODEL


def transcribe_wav(path: str, language: str | None) -> tuple[list[dict], str | None]:
    it, info = _get_model().transcribe(
        path,
        language=language,                       # None = auto-detect; pass "hi" if you know it
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        word_timestamps=True,
        beam_size=5,
        initial_prompt=settings.whisper_initial_prompt,
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
    "You are an expert dialogue parser for loan-officer field interviews in India (supporting any regional language, Hindi, Hinglish, or English). "
    "There are two speakers: 'officer' and 'borrower'. "
    "Tasks:\n"
    "1. If a segment contains BOTH an officer question and borrower reply, split them into separate dialogue turns.\n"
    "2. Correct transcription phonetic typos into clean grammar in the spoken language while preserving numbers, amounts, and names.\n"
    'Return JSON only: {"turns": [{"segment_index": <int>, "speaker": "officer" | "borrower" | "unknown", "text": "<clean text>"}]}'
)


def tag_speakers(llm, segments: list[dict]) -> tuple[list[dict], list[str]]:
    """Identifies dialogue turns, splits mixed Q&A turns, and polishes transcript text.

    Returns (refined_segments, speaker_labels).
    """
    if not segments:
        return [], []

    try:
        user_payload = json.dumps({
            "segments": [{"segment_index": i, "text": s["text"]} for i, s in enumerate(segments)]
        }, ensure_ascii=False)

        res = llm.complete_json(SPEAKER_SYSTEM_PROMPT, user_payload)
        turns = res.get("turns", [])

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
            total_chars = sum(len(t.get("text", "")) for t in sub_turns) or 1

            cur_start = orig_seg["start"]
            for i, turn in enumerate(sub_turns):
                spk = turn.get("speaker", "borrower")
                if spk not in SPEAKER_LABELS:
                    spk = "borrower"
                turn_text = turn.get("text", orig_seg["text"]).strip()
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


# ====================== 4. Entry point ======================
def run_stt(session_id: str, llm) -> str:
    """Celery entry point. Idempotent: re-running replaces earlier transcript rows. Returns session_id."""
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
                conf, min_w = segment_confidence(seg["words"], seg["avg_logprob"])
                db.add(TranscriptSegment(
                    pd_session_id=session_id, seq=seq,
                    start_time=seg["start"], end_time=seg["end"],
                    speaker=spk, text=seg["text"], confidence=conf, min_word_conf=min_w,
                    low_confidence=conf < settings.low_conf_threshold,
                ))
            s.transcript_raw = "\n".join(f"[{spk}] {seg['text']}" for seg, spk in zip(segs, speakers))
            s.raw_asr_json = {"model": f"faster-whisper:{settings.whisper_model}", "language": language,
                              "pieces": pieces, "segments": segs}
            s.duration_sec, s.language, s.status = duration, language, "transcribed"
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