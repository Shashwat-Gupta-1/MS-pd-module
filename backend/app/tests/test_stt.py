import pytest
from app.utils.stt_utils import (
    parse_silences,
    plan_pieces,
    dedupe_segments,
    split_segments_by_word_gaps,
    segment_confidence,
    looks_like_question,
    heuristic_tag
)
from app.agents.llm_client import get_llm, GeminiClient, GroqClient


def test_parse_silences():
    fake_stderr = """
    [silencedetect @ 000001] silence_start: 12.35
    [silencedetect @ 000001] silence_end: 15.60 | silence_duration: 3.25
    [silencedetect @ 000001] silence_start: 45.10
    [silencedetect @ 000001] silence_end: 48.00 | silence_duration: 2.90
    """
    silences = parse_silences(fake_stderr)
    assert len(silences) == 2
    assert silences[0] == (12.35, 15.60)
    assert silences[1] == (45.10, 48.00)


def test_plan_pieces_short_audio():
    silences = [(10.0, 12.0)]
    pieces = plan_pieces(silences, duration=100.0, target=60.0)
    assert len(pieces) >= 1
    assert pieces[0][0] == 0.0
    assert pieces[-1][1] == 100.0


def test_dedupe_segments():
    segs = [
        {"start": 0.0, "end": 5.0, "text": "Hello"},
        {"start": 4.5, "end": 8.0, "text": "Duplicate overlap"},  # 4.5 < (5.0 - 0.25 = 4.75), skipped
        {"start": 5.5, "end": 10.0, "text": "World"}
    ]
    deduped = dedupe_segments(segs, eps=0.25)
    assert len(deduped) == 2
    assert deduped[0]["text"] == "Hello"
    assert deduped[1]["text"] == "World"


def test_split_segments_by_word_gaps():
    seg = {
        "start": 0.0,
        "end": 6.0,
        "text": "Aapka business kitne saal se hai? Dus saal.",
        "avg_logprob": -0.2,
        "no_speech_prob": 0.01,
        "words": [
            {"w": "Aapka", "start": 0.0, "end": 0.5, "p": 0.95},
            {"w": "business", "start": 0.6, "end": 1.2, "p": 0.96},
            {"w": "hai?", "start": 1.3, "end": 1.8, "p": 0.94},
            # Gap of 1.4s (3.2 - 1.8 = 1.4 >= min_gap 0.8)
            {"w": "Dus", "start": 3.2, "end": 3.8, "p": 0.91},
            {"w": "saal.", "start": 3.9, "end": 4.5, "p": 0.92},
        ]
    }
    split = split_segments_by_word_gaps([seg], min_gap_sec=0.8)
    assert len(split) == 2
    assert "Aapka" in split[0]["text"]
    assert "Dus" in split[1]["text"]


def test_segment_confidence():
    words = [
        {"w": "word1", "p": 0.9},
        {"w": "word2", "p": 0.8},
    ]
    conf, min_w = segment_confidence(words, avg_logprob=-0.15)
    assert pytest.approx(conf, 0.01) == 0.85
    assert pytest.approx(min_w, 0.01) == 0.8


def test_looks_like_question():
    assert looks_like_question("Kitna turnover hota hai daily?") is True
    assert looks_like_question("Aapka loan pehle kabhi default hua?") is True
    assert looks_like_question("Daily sales around 5000 hoti hai") is False


def test_heuristic_tag():
    segs = [
        {"text": "Dukaan ka kiraya kitna hai?"},
        {"text": "Rs 8000 per month."},
        {"text": "Pehle koi aur loan liya tha?"},
        {"text": "Nahi sir, bilkul nahi."},
    ]
    tags = heuristic_tag(segs)
    assert tags[0] == "officer"
    assert tags[1] == "borrower"
    assert tags[2] == "officer"
    assert tags[3] == "borrower"


def test_get_llm_factory():
    llm = get_llm()
    assert hasattr(llm, "complete_json")
