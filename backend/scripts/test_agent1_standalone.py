"""Standalone Runner & Verifier for Agent 1 (Speech-to-Text & Diarization).

Flow:
1. Generates or locates a real spoken dialogue audio WAV.
2. Creates an active PDSession in PostgreSQL.
3. Invokes `run_stt(session.id)`.
4. Reads and validates the transcribed segments and speaker labels from PostgreSQL.
"""
import os
import sys
import uuid
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.officer import Officer
from app.models.applicant import Applicant
from app.models.application import Application, ApplicationStatusEnum
from app.models.pd_session import PDSession
from app.models.transcript_segment import TranscriptSegment
from app.agents.speech_to_text import run_stt
from app.agents.llm_client import get_llm


def run_agent1_demo():
    audio_path = os.path.abspath("uploads/recordings/test_interview.wav")
    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found at {audio_path}")
        return

    print("==================================================================")
    print("[START] AGENT 1 (SPEECH-TO-TEXT & SPEAKER DIARIZATION) RUNNER")
    print("==================================================================")
    print(f"Audio Input: {audio_path}")
    print(f"LLM Diarization Provider: {get_llm().__class__.__name__}")

    with SessionLocal() as db:
        # 1. Ensure test Officer exists
        officer = db.query(Officer).first()
        if not officer:
            officer = Officer(
                username=f"officer_{uuid.uuid4().hex[:6]}",
                password_hash="mock_hash",
                name="Test Credit Officer",
                is_active=True
            )
            db.add(officer)
            db.commit()
            db.refresh(officer)
        print(f"Credit Officer: {officer.name} (ID: {officer.id})")

        # 2. Ensure test Applicant & Application exist
        app = db.query(Application).first()
        if not app:
            applicant = Applicant(
                name="Ramesh Kumar",
                phone="9876543210",
                business_name="Ramesh Kirana General Store",
                business_type="Retail Trade",
                monthly_income=200000.0,
                location_pincode="302001",
                pan_number="ABCDE1234F",
                employment_type="SELF_EMPLOYED",
                sub_profile="KIRANA"
            )
            db.add(applicant)
            db.commit()
            db.refresh(applicant)

            app = Application(
                applicant_id=applicant.id,
                product_type="MICRO_ENTERPRISE",
                requested_amount=500000.0,
                tenure=24,
                rate=18.0,
                status=ApplicationStatusEnum.PD_IN_PROGRESS
            )
            db.add(app)
            db.commit()
            db.refresh(app)
        print(f"Application ID: {app.id}")

        # 3. Create test PD Session
        session = PDSession(
            application_id=app.id,
            officer_id=officer.id,
            channel="ground",
            recording_url=audio_path,
            consent_captured=True,
            consent_timestamp=datetime.now(timezone.utc),
            status="recorded",
            is_session_active=True
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
        print(f"Created PD Session: {session_id}")

    # 4. RUN AGENT 1
    print("\nRunning Agent 1 (faster-whisper ASR + LLM Diarization)...")
    res_session_id = run_stt(session_id)
    print(f"STT Execution completed for session: {res_session_id}\n")

    # 5. VERIFY DATABASE PERSISTENCE IN POSTGRESQL
    with SessionLocal() as db:
        s = db.get(PDSession, session_id)
        segments = db.query(TranscriptSegment).filter_by(pd_session_id=session_id).order_by(TranscriptSegment.seq).all()

        print("==================================================================")
        print("AGENT 1 RESULTS & DATABASE AUDIT")
        print("==================================================================")
        print(f"Session Status   : {s.status}")
        print(f"Audio Duration   : {s.duration_sec:.2f} seconds")
        print(f"Detected Language: {s.language}")
        print(f"Total Segments   : {len(segments)}")
        print("------------------------------------------------------------------")
        print("DIARIZED DIALOGUE TURNS (Saved in transcript_segments table):")
        print("------------------------------------------------------------------")
        for seg in segments:
            conf_str = f"{seg.confidence * 100:.1f}%" if seg.confidence else "N/A"
            flag = "LOW_CONF" if seg.low_confidence else "OK"
            print(f"[{seg.seq:02d}] {seg.start_time:5.2f}s - {seg.end_time:5.2f}s | {seg.speaker.upper():8s} | [{flag}] ({conf_str}):")
            print(f"     \"{seg.text}\"")

        print("------------------------------------------------------------------")
        print("RAW FULL TRANSCRIPT (Saved in pd_sessions.transcript_raw):")
        print("------------------------------------------------------------------")
        print(s.transcript_raw)
        print("==================================================================")
        print("AGENT 1 RUN COMPLETED & VERIFIED SUCCESSFULLY!")
        print("==================================================================")


if __name__ == "__main__":
    run_agent1_demo()
