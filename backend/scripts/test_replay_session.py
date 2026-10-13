import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Configure stdout for utf-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.application import Application
from app.models.pd_session import PDSession
from app.agents.speech_to_text import transcribe_chunk_bytes
from app.agents.pd_workflow_graph import pd_graph, PDWorkflowState
from app.agents.report_assembly import compile_cam_data
from app.agents.llm_client import get_llm


def run_audio_replay():
    session_id = "45fcfac5-2401-4da1-a60b-c5ff16c43db9"
    app_id = "3709da80-4c7f-452c-ad0d-186280aa9a4b"
    recordings_dir = Path("uploads/recordings")

    # Locate all batches for this session
    batch_files = sorted(
        recordings_dir.glob(f"{session_id}_batch_*.webm"),
        key=lambda p: int(p.stem.split("_batch_")[-1])
    )

    print(f"\n{'='*80}")
    print(f"🎙️ AUDIO REPLAY TEST: Case {app_id} | Session {session_id}")
    print(f"📂 Found {len(batch_files)} recorded audio batches in {recordings_dir}")
    print(f"{'='*80}\n")

    if not batch_files:
        print("❌ No audio batch files found!")
        return

    db = SessionLocal()
    app_obj = db.query(Application).filter(Application.id == app_id).first()
    if not app_obj:
        print(f"❌ Application {app_id} not found in database!")
        db.close()
        return

    applicant = app_obj.applicant
    sub_profile = (applicant.sub_profile or "DAIRY").upper() if applicant else "DAIRY"
    emp_type = "SELF_EMPLOYED"

    # Initialize LLM for diarization
    diarization_llm = get_llm(provider="gemini", task="diarization")

    # Initialize cumulative state
    state = {
        "session_id": session_id,
        "application_id": app_id,
        "employment_type": emp_type,
        "sub_profile": sub_profile,
        "rag_requirements": {},
        "dynamic_questionnaire": [],
        "transcript_history": [],
        "current_batch": [],
        "batch_index": 0,
        "extracted_fields": {},
        "active_followup_questions": [],
        "resolved_followup_questions": [],
        "round_number": 0,
        "officer_uptake_count": 0,
        "officer_proactive_bonus_points": 0,
        "customer_contradiction_count": 0,
        "detected_contradictions": [],
        "gaps_remaining": True,
        "is_session_active": True,
    }

    cumulative_extracted = {}
    all_transcripts = []

    # Process batches
    for batch_idx, batch_path in enumerate(batch_files):
        print(f"\n--- [BATCH #{batch_idx}: {batch_path.name}] ---")
        with open(batch_path, "rb") as f:
            chunk_bytes = f.read()

        print(f"Size: {len(chunk_bytes)} bytes | Transcribing with Groq Whisper + Detailed Prompt...")
        try:
            segments = transcribe_chunk_bytes(
                chunk_bytes=chunk_bytes,
                language="hi",
                session_id=None,  # don't re-save over existing files
                chunk_sequence=batch_idx,
                llm=diarization_llm,
                prompt=settings.whisper_initial_prompt
            )
        except Exception as e:
            print(f"⚠️ STT error on batch {batch_idx}: {e}")
            segments = []

        if not segments:
            print("   (Silence / no speech detected)")
            continue

        print(f"🎤 Transcribed {len(segments)} segments:")
        for s in segments:
            spk = s.get("speaker", "borrower").upper()
            txt = s.get("text", "")
            print(f"   [{spk}]: \"{txt}\"")
            all_transcripts.append(f"[{spk}]: {txt}")

        # Feed to LangGraph
        state["current_batch"] = segments
        state["batch_index"] = batch_idx
        state["round_number"] = batch_idx + 1

        try:
            result = pd_graph.invoke(state, config={"configurable": {"thread_id": f"test_{session_id}_{batch_idx}"}})
            state = result

            extracted_now = result.get("extracted_fields", {})
            cumulative_extracted.update(extracted_now)
            active_qs = result.get("active_followup_questions", [])
            contradictions = result.get("detected_contradictions", [])

            print(f"📊 Node 3 Fields Extracted in this turn: {len(extracted_now)}")
            for k, v in list(extracted_now.items())[-4:]:
                print(f"   • {k}: {v.get('value')} ({v.get('status', 'extracted')})")

            if active_qs:
                print(f"❓ Node 6 Active Follow-up Questions ({len(active_qs)}):")
                for q in active_qs[:3]:
                    print(f"   • [{q.get('category')}]: {q.get('question_text')}")

            if contradictions:
                print(f"⚠️ Node 5 Contradictions Detected: {len(contradictions)}")
                for c in contradictions:
                    print(f"   • {c.get('field_name')}: \"{c.get('stated_value_1')}\" vs \"{c.get('stated_value_2')}\"")

        except Exception as graph_err:
            print(f"⚠️ LangGraph execution error: {graph_err}")

    print(f"\n{'='*80}")
    print("📈 FINAL SUMMARY OF EXTRACTION & ANALYSIS ACROSS ALL BATCHES")
    print(f"{'='*80}")
    print(f"Total Unique Fields Captured: {len(cumulative_extracted)}")
    for k, v in cumulative_extracted.items():
        print(f"  • {k:40} : {v.get('value')} [{v.get('status', 'inferred')}]")

    # Generate and display CAM report
    print(f"\n{'='*80}")
    print("📋 COMPILED CREDIT ASSESSMENT MEMORANDUM (CAM)")
    print(f"{'='*80}")
    cam = compile_cam_data(app_id, db)
    db.close()

    print(f"Case Number         : {cam.get('case_number')}")
    print(f"Applicant           : {cam.get('applicant_name')} ({cam.get('applicant_phone')})")
    print(f"Employment Profile  : {cam.get('employment_type')} | Sub-Profile: {cam.get('sub_profile')}")
    print(f"Requested Amount    : ₹{cam.get('requested_amount_str')}")
    print(f"Tenure              : {cam.get('tenure_months')} Months")
    print(f"Calculated EMI      : ₹{cam.get('proposed_emi_str')}")
    print(f"Final FOIR          : {cam.get('final_foir_str')}%")
    print(f"Final LTV           : {cam.get('final_ltv_str') or 'Unsecured'}")
    print(f"BRE Recommendation  : {cam.get('bre_recommendation')}")
    print(f"\n--- [Business Verification Narrative] ---")
    print(cam.get('business_overview'))
    print(f"\n--- [Financial Assessment Narrative] ---")
    print(cam.get('financial_overview'))
    print(f"\n--- [Verified Ground Extracted Data ({len(cam.get('extracted_fields', []))} fields)] ---")
    for ef in cam.get('extracted_fields', []):
        print(f"  • {ef['name']:38} : {ef['value']} [{ef['source']}] (Confirmed: {ef['confirmed']})")
    print(f"\n--- [Consistency Flags ({len(cam.get('consistency_flags', []))})] ---")
    for cf in cam.get('consistency_flags', []):
        print(f"  ⚠️ {cf['field_name']}: '{cf['value_a']}' vs '{cf['value_b']}' ({cf['severity']})")
    print(f"\n--- [Officer Diligence Scores] ---")
    print(f"  Coverage: {cam.get('officer_coverage_score')}% | Uptake: {cam.get('officer_uptake_score')}% | Bonus: +{cam.get('officer_proactive_bonus')} pts")
    print(f"  Overall Underwriter Diligence: {cam.get('officer_overall_score')} / 100")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    run_audio_replay()
