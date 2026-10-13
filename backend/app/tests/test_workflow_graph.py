import os
import json
import pytest
from app.agents.pd_workflow_graph import (
    pd_graph,
    ingest_batch,
    evaluate_diligence,
    extract_fields,
    check_consistency,
    analyze_gaps,
    generate_followups,
    mark_resolved,
    persist_batch_results,
    PDWorkflowState
)
from app.models.applicant import Applicant, EmploymentTypeEnum
from app.models.application import Application, ApplicationStatusEnum
from app.models.officer import Officer
from app.models.pd_session import PDSession
from app.models.transcript_segment import TranscriptSegment
from app.models.extracted_field import ExtractedField
from app.models.gap_question import GapQuestion
from app.models.customer_consistency_flag import CustomerConsistencyFlag


@pytest.fixture
def workflow_setup(db_session):
    officer = Officer(name="Field Officer", phone_number="9876543210", hashed_password="pw", role="OFFICER")
    db_session.add(officer)
    db_session.commit()

    applicant = Applicant(
        full_name="Ramesh Kumar",
        phone_number="9123456789",
        pan_number="ABCDE1234F",
        employment_type=EmploymentTypeEnum.SELF_EMPLOYED,
        sub_profile="RETAIL"
    )
    db_session.add(applicant)
    db_session.commit()

    app = Application(
        case_number="APP-2026-TEST",
        applicant_id=applicant.id,
        loan_type="BUSINESS_LOAN",
        requested_amount=500000.0,
        status=ApplicationStatusEnum.PD_IN_PROGRESS
    )
    db_session.add(app)
    db_session.commit()

    session = PDSession(
        application_id=app.id,
        officer_id=officer.id,
        channel="ground",
        status="recorded",
        is_session_active=True
    )
    db_session.add(session)
    db_session.commit()

    return session


def test_node1_ingest_batch_deduplication():
    state: PDWorkflowState = {
        "session_id": "sess-1",
        "application_id": "app-1",
        "employment_type": "SELF_EMPLOYED",
        "sub_profile": "RETAIL",
        "rag_requirements": {},
        "transcript_history": [
            {"start_time": 0.0, "end_time": 5.0, "speaker": "OFFICER", "text": "Namaste"}
        ],
        "current_batch": [
            {"start_time": 0.0, "end_time": 5.0, "speaker": "OFFICER", "text": "Namaste"},  # Duplicate
            {"start_time": 5.5, "end_time": 10.0, "speaker": "APPLICANT", "text": "Namaste sir, welcome"}
        ],
        "batch_index": 1,
        "extracted_fields": {},
        "active_followup_questions": [],
        "resolved_followup_questions": [],
        "round_number": 1,
        "officer_uptake_count": 0,
        "officer_proactive_bonus_points": 0,
        "customer_contradiction_count": 0,
        "detected_contradictions": [],
        "gaps_remaining": True,
        "is_session_active": True
    }

    new_state = ingest_batch(state)
    assert len(new_state["transcript_history"]) == 2
    assert new_state["transcript_history"][1]["text"] == "Namaste sir, welcome"


def test_node2_evaluate_diligence_uptake_and_proactive_bonus():
    state: PDWorkflowState = {
        "session_id": "sess-2",
        "application_id": "app-2",
        "employment_type": "SELF_EMPLOYED",
        "sub_profile": "RETAIL",
        "rag_requirements": {},
        "transcript_history": [],
        "current_batch": [
            {
                "start_time": 10.0,
                "end_time": 25.0,
                "speaker": "OFFICER",
                "text": "What are your supplier credit terms and lease stability in this market?"
            },
            {
                "start_time": 25.5,
                "end_time": 35.0,
                "speaker": "APPLICANT",
                "text": "Suppliers give 15 days credit, and our lease is renewed for 5 years."
            }
        ],
        "batch_index": 2,
        "extracted_fields": {},
        "active_followup_questions": [
            {"question_text": "What is your supplier payment terms?", "category": "SUPPLIER"}
        ],
        "resolved_followup_questions": [],
        "round_number": 2,
        "officer_uptake_count": 0,
        "officer_proactive_bonus_points": 0,
        "customer_contradiction_count": 0,
        "detected_contradictions": [],
        "gaps_remaining": True,
        "is_session_active": True
    }

    updated = evaluate_diligence(state)
    assert updated["officer_uptake_count"] == 1
    assert len(updated["resolved_followup_questions"]) == 1
    assert len(updated["active_followup_questions"]) == 0
    assert updated["officer_proactive_bonus_points"] >= 1


def test_node3_field_extraction_and_numeric_reconfirmation():
    state: PDWorkflowState = {
        "session_id": "sess-3",
        "application_id": "app-3",
        "employment_type": "SELF_EMPLOYED",
        "sub_profile": "RETAIL",
        "rag_requirements": {},
        "transcript_history": [],
        "current_batch": [
            {
                "start_time": 0.0,
                "end_time": 15.0,
                "speaker": "APPLICANT",
                "text": "My monthly turnover is 2,50,000 rupees and profit margin is 12%."
            }
        ],
        "batch_index": 1,
        "extracted_fields": {},
        "active_followup_questions": [],
        "resolved_followup_questions": [],
        "round_number": 1,
        "officer_uptake_count": 0,
        "officer_proactive_bonus_points": 0,
        "customer_contradiction_count": 0,
        "detected_contradictions": [],
        "gaps_remaining": True,
        "is_session_active": True
    }

    res = extract_fields(state)
    assert "monthly_turnover" in res["extracted_fields"]
    assert res["extracted_fields"]["monthly_turnover"]["value"] == 250000.0
    assert res["extracted_fields"]["monthly_turnover"]["needs_reconfirmation"] is True


def test_node4_consistency_check_flags_contradiction():
    state: PDWorkflowState = {
        "session_id": "sess-4",
        "application_id": "app-4",
        "employment_type": "SELF_EMPLOYED",
        "sub_profile": "RETAIL",
        "rag_requirements": {},
        "transcript_history": [
            {
                "start_time": 0.0,
                "end_time": 15.0,
                "speaker": "APPLICANT",
                "text": "My annual turnover is easily 20,00,000 rupees."
            },
            {
                "start_time": 15.5,
                "end_time": 30.0,
                "speaker": "APPLICANT",
                "text": "Daily sales are around 2,000 rupees on normal days."
            }
        ],
        "current_batch": [
            {
                "start_time": 15.5,
                "end_time": 30.0,
                "speaker": "APPLICANT",
                "text": "Daily sales are around 2,000 rupees on normal days."
            }
        ],
        "batch_index": 2,
        "extracted_fields": {},
        "active_followup_questions": [],
        "resolved_followup_questions": [],
        "round_number": 2,
        "officer_uptake_count": 0,
        "officer_proactive_bonus_points": 0,
        "customer_contradiction_count": 0,
        "detected_contradictions": [],
        "gaps_remaining": True,
        "is_session_active": True
    }

    res = check_consistency(state)
    assert res["customer_contradiction_count"] >= 1
    assert len(res["detected_contradictions"]) >= 1
    assert res["detected_contradictions"][0]["severity"] == "HIGH"


def test_node5_cost_guard_skips_short_batch():
    state: PDWorkflowState = {
        "session_id": "sess-5",
        "application_id": "app-5",
        "employment_type": "SELF_EMPLOYED",
        "sub_profile": "RETAIL",
        "rag_requirements": {"required_info_checklist_json": ["monthly_turnover"]},
        "transcript_history": [],
        "current_batch": [
            {"start_time": 0.0, "end_time": 3.0, "speaker": "APPLICANT", "text": "Ji bilkul haan."}  # Only 3 words
        ],
        "batch_index": 3,
        "extracted_fields": {},
        "active_followup_questions": [],
        "resolved_followup_questions": [],
        "round_number": 3,
        "officer_uptake_count": 0,
        "officer_proactive_bonus_points": 0,
        "customer_contradiction_count": 0,
        "detected_contradictions": [],
        "gaps_remaining": True,
        "is_session_active": True
    }

    # Should skip LLM gap check without error
    res = analyze_gaps(state)
    assert res["gaps_remaining"] is True


def test_full_graph_invocation_and_persistence(db_session, workflow_setup):
    session = workflow_setup
    session_id = str(session.id)
    app_id = str(session.application_id)
    config = {"configurable": {"thread_id": session_id}}

    batch_input: PDWorkflowState = {
        "session_id": session_id,
        "application_id": app_id,
        "employment_type": "SELF_EMPLOYED",
        "sub_profile": "RETAIL",
        "rag_requirements": {},
        "transcript_history": [],
        "current_batch": [
            {
                "start_time": 0.0,
                "end_time": 20.0,
                "speaker": "APPLICANT",
                "text": "My monthly turnover is 2,50,000 rupees and profit margin is 12 percent. We need working capital."
            }
        ],
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
        "is_session_active": True
    }

    # Invoke graph
    final_state = pd_graph.invoke(batch_input, config=config)
    assert "transcript_history" in final_state
    assert len(final_state["transcript_history"]) >= 1

    # Persist results
    active_qs = persist_batch_results(final_state, db_session)
    assert isinstance(active_qs, list)

    # Verify DB persistence
    segments = db_session.query(TranscriptSegment).filter(TranscriptSegment.pd_session_id == session_id).all()
    assert len(segments) >= 1

    fields = db_session.query(ExtractedField).filter(ExtractedField.pd_session_id == session_id).all()
    assert len(fields) >= 1
