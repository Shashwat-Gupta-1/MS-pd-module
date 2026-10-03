"""Pure helpers for Agent 1 (no heavy imports, so they are unit-testable)."""
import math
import re

QUESTION_STARTERS = (
    "kya", "kitna", "kitne", "kitni", "kab", "kaise", "kahan", "kaun", "kyun", "kyu", "kis", "koi",
    "what", "how", "when", "where", "why", "who", "which", "do you", "did you", "is ", "are ", "can ", "could ",
    "क्या", "कितना", "कितने", "कितनी", "कब", "कैसे", "कहाँ", "कहा", "क्यों", "क्यु", "किस", "कोई", "कौन",
)


def parse_silences(ffmpeg_stderr: str) -> list[tuple[float, float]]:
    """Parse ffmpeg `silencedetect` output into (start, end) pairs. A trailing unmatched start is dropped."""
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", ffmpeg_stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", ffmpeg_stderr)]
    return list(zip(starts, ends))


def plan_pieces(silences: list[tuple[float, float]], duration: float, target: float = 600.0) -> list[tuple[float, float]]:
    """Cut long audio into ~target-second pieces, always at the longest silence near the target."""
    pieces: list[tuple[float, float]] = []
    cursor = 0.0
    while duration - cursor > target * 1.5:
        lo, hi = cursor + target * 0.8, cursor + target * 1.2
        cands = [(e - s, (s + e) / 2) for s, e in silences if lo <= (s + e) / 2 <= hi]
        cut = max(cands)[1] if cands else cursor + target
        pieces.append((cursor, cut))
        cursor = cut
    pieces.append((cursor, duration))
    return pieces


def dedupe_segments(segs: list[dict], eps: float = 0.25) -> list[dict]:
    """Remove segments repeated in the overlap between two audio pieces (absolute-time segments)."""
    out: list[dict] = []
    last_end = -1.0
    for s in sorted(segs, key=lambda x: x["start"]):
        if out and s["start"] < last_end - eps:
            continue
        out.append(s)
        last_end = s["end"]
    return out


def split_segments_by_word_gaps(segs: list[dict], min_gap_sec: float = 0.8) -> list[dict]:
    """Split Whisper segments if there is a silence pause >= min_gap_sec between consecutive words."""
    out: list[dict] = []
    for seg in segs:
        words = seg.get("words", [])
        if not words or len(words) <= 1:
            out.append(seg)
            continue

        chunk_words = [words[0]]
        for i in range(1, len(words)):
            # Check gap between previous word end and current word start
            gap = words[i]["start"] - words[i - 1]["end"]
            if gap >= min_gap_sec:
                text_chunk = "".join([w["w"] for w in chunk_words]).strip()
                out.append({
                    "start": chunk_words[0]["start"],
                    "end": chunk_words[-1]["end"],
                    "text": text_chunk,
                    "avg_logprob": seg.get("avg_logprob"),
                    "no_speech_prob": seg.get("no_speech_prob"),
                    "words": chunk_words,
                })
                chunk_words = [words[i]]
            else:
                chunk_words.append(words[i])

        if chunk_words:
            text_chunk = "".join([w["w"] for w in chunk_words]).strip()
            out.append({
                "start": chunk_words[0]["start"],
                "end": chunk_words[-1]["end"],
                "text": text_chunk,
                "avg_logprob": seg.get("avg_logprob"),
                "no_speech_prob": seg.get("no_speech_prob"),
                "words": chunk_words,
            })
    return out


def segment_confidence(words: list[dict], avg_logprob: float | None) -> tuple[float, float | None]:
    """Return (segment confidence, min word confidence)."""
    probs = [w["p"] for w in words if w.get("p") is not None]
    if probs:
        return sum(probs) / len(probs), min(probs)
    if avg_logprob is not None:
        return max(0.0, min(1.0, math.exp(avg_logprob))), None
    return 0.0, None


def looks_like_question(text: str) -> bool:
    t = text.strip().lower()
    if t.endswith("?") or t.startswith(QUESTION_STARTERS):
        return True
    words = re.findall(r"[\w']+", t)
    if any(w in QUESTION_STARTERS for w in words):
        return True
    return False


def heuristic_tag(segments: list[dict]) -> list[str]:
    """Fallback speaker labels when the LLM is unavailable. Officers ask; borrowers answer."""
    labels = []
    for i, s in enumerate(segments):
        text = s["text"]
        if looks_like_question(text):
            labels.append("officer")
        elif len(text.split()) <= 4 and i > 0 and labels[-1] == "officer":
            labels.append("borrower")           # direct reply right after a question
        elif text.strip().startswith(("जी", "ji", "yes", "ha", "haan", "nahi", "no")):
            labels.append("borrower")
        else:
            labels.append("borrower")
    return labels
