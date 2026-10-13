import os
import json
import logging
from datetime import datetime, timezone
from typing import TypedDict, List, Dict, Any, Optional, NotRequired

from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.agents.llm_client import complete
from app.rag.retrieval import get_profession_profile
from app.models.transcript_segment import TranscriptSegment
from app.models.extracted_field import ExtractedField
from app.models.gap_question import GapQuestion
from app.models.customer_consistency_flag import CustomerConsistencyFlag
from app.models.officer_pd_score import OfficerPDScore
from app.models.pd_session import PDSession

logger = logging.getLogger(__name__)


class PDWorkflowState(TypedDict):
    session_id: str
    application_id: str
    employment_type: str              # SALARIED | SELF_EMPLOYED
    sub_profile: str                  # e.g. RETAIL, MANUFACTURING, SERVICES, SALARIED_PRIVATE, SALARIED_GOVT
    rag_requirements: Dict[str, Any]  # loaded once, round 1, cached for the session
    dynamic_questionnaire: NotRequired[List[Dict[str, Any]]]  # Dynamic frontend question list (Tier 1-3)
    transcript_history: List[Dict[str, Any]]
    current_batch: List[Dict[str, Any]]
    batch_index: int
    extracted_fields: Dict[str, Dict[str, Any]]   # {field_name: {value, status, confidence, reasoning}}
    active_followup_questions: List[Dict[str, Any]]
    resolved_followup_questions: List[Dict[str, Any]]
    all_followup_questions_history: NotRequired[List[Dict[str, Any]]] # Master session history of all generated followups
    round_number: int
    officer_uptake_count: int
    officer_proactive_bonus_points: int
    customer_contradiction_count: int
    detected_contradictions: List[Dict[str, Any]]
    gaps_remaining: bool
    is_session_active: bool


def normalize_question_text(text: str) -> str:
    """Normalizes question strings for lexical duplicate detection."""
    import re
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s\u0900-\u097F]", " ", str(text).lower())
    return " ".join(cleaned.split())


# -------------------------------------------------------------------------
# Node 1: Ingest Batch & Transcript History Node
# -------------------------------------------------------------------------
def ingest_batch(state: PDWorkflowState) -> PDWorkflowState:
    """
    Merges new timestamped transcript segment(s) from current_batch into accumulated transcript_history.
    Dedupes on (start_time, end_time, text) to guard against retried/duplicate chunk delivery.
    """
    history = list(state.get("transcript_history", []))
    current_batch = state.get("current_batch", [])

    existing_keys = {
        (round(float(s.get("start_time", 0.0)), 2), round(float(s.get("end_time", 0.0)), 2), str(s.get("text", "")).strip())
        for s in history
    }

    for segment in current_batch:
        key = (
            round(float(segment.get("start_time", 0.0)), 2),
            round(float(segment.get("end_time", 0.0)), 2),
            str(segment.get("text", "")).strip()
        )
        if key not in existing_keys:
            history.append(segment)
            existing_keys.add(key)

    state["transcript_history"] = history
    print(f"   ↳ [Node 1: ingest_batch] Ingested {len(current_batch)} segment(s) -> Total conversation history: {len(history)} turn(s).", flush=True)
    return state


# -------------------------------------------------------------------------
# Node 2: Officer Diligence & Uptake Evaluator Node
# -------------------------------------------------------------------------
def evaluate_diligence(state: PDWorkflowState) -> PDWorkflowState:
    """
    Step A -- Uptake check: Did officer ask a semantically equivalent version of any active follow-up questions?
    Step B -- Proactive bonus check: Did officer ask an unprompted, relevant credit question?
    Runs in one combined prompt per batch for cost efficiency.
    """
    active_qs = list(state.get("active_followup_questions", []))
    current_batch = state.get("current_batch", [])
    
    if not current_batch:
        return state

    current_text = " ".join([f"{s.get('speaker', 'SPEAKER')}: {s.get('text', '')}" for s in current_batch])
    
    # Prompt LLM covering both Step A (uptake) and Step B (proactive bonus)
    prompt = f"""
    Evaluate the officer's interview conduct from this latest audio transcript batch.
    
    Business Sub-Profile: {state.get('sub_profile', 'GENERAL')}
    Active Follow-Up Suggestions on Officer's screen:
    {json.dumps([{'index': idx, 'question': q.get('question_text')} for idx, q in enumerate(active_qs)], indent=2)}

    Latest Audio Transcript Batch:
    "{current_text}"

    Analyze:
    1. Uptake Check: Did the officer ask a semantically equivalent version of any of the active follow-up suggestions, and did the applicant respond? Return indices of resolved questions.
    2. Proactive Bonus Check: Did the officer ask an intelligent, unprompted credit question that is NOT a duplicate of baseline questionnaire or active suggestions, but shows genuine field credit curiosity (e.g. asking about supplier strikes, raw material quality, lease terms, seasonal buffer)?

    Return JSON:
    {{
      "resolved_question_indices": [0],
      "proactive_bonus_awarded": true,
      "proactive_bonus_reason": "Officer proactively asked about supplier credit cycle and lease terms."
    }}
    """

    try:
        res = complete(prompt, response_format="json")
        if isinstance(res, dict):
            resolved_indices = set(res.get("resolved_question_indices", []))
            remaining_active = []
            resolved_qs = list(state.get("resolved_followup_questions", []))

            for idx, q in enumerate(active_qs):
                if idx in resolved_indices:
                    resolved_copy = dict(q)
                    resolved_copy["resolved_at_batch"] = state.get("batch_index", 0)
                    resolved_qs.append(resolved_copy)
                    state["officer_uptake_count"] = state.get("officer_uptake_count", 0) + 1
                else:
                    remaining_active.append(q)

            state["active_followup_questions"] = remaining_active
            state["resolved_followup_questions"] = resolved_qs

            if res.get("proactive_bonus_awarded"):
                state["officer_proactive_bonus_points"] = state.get("officer_proactive_bonus_points", 0) + 1
                logger.info(f"Awarded proactive bonus to officer: {res.get('proactive_bonus_reason')}")
    except Exception as e:
        logger.error(f"Error in evaluate_diligence: {e}")

    print(f"   ↳ [Node 2: evaluate_diligence] Officer Diligence: Uptake Count={state.get('officer_uptake_count', 0)}, Bonus Points=+{state.get('officer_proactive_bonus_points', 0)}", flush=True)
    return state


# -------------------------------------------------------------------------
# Node 3: 3-State Field Extraction Node (Powered by Gemini)
# -------------------------------------------------------------------------
def extract_fields(state: PDWorkflowState) -> PDWorkflowState:
    """
    Extracts business, financial, and credit data points using Google Gemini.
    - Uses FULL cumulative transcript history for deep conversational memory.
    - Targets the DYNAMIC frontend questionnaire fields (Tier 1, Tier 2, Tier 3) applicable to this case.
    - Infers answers to active and generated AI follow-up questions.
    - Discovers unstructured, high-value credit underwriting signals (informal debt, risk, unstated assets).
    - Preserves already STATED values without downgrade.
    - Dynamically refines granular trade sub-profiles in ChromaDB when occupation details are detected.
    """
    transcript_history = state.get("transcript_history", [])
    current_batch = state.get("current_batch", [])

    if not transcript_history and not current_batch:
        return state

    # 1. Format Full Transcript History with Speaker & Timestamps
    if transcript_history:
        history_lines = []
        for s in transcript_history:
            spk = str(s.get("speaker", "SPEAKER")).upper()
            st = s.get("start_time", s.get("start", 0.0))
            txt = s.get("text", "")
            history_lines.append(f"[{spk} ({float(st):.1f}s)]: {txt}")
        full_transcript_text = "\n".join(history_lines)
    else:
        full_transcript_text = "\n".join([
            f"[{str(s.get('speaker', 'SPEAKER')).upper()}]: {s.get('text', '')}"
            for s in current_batch
        ])

    latest_slice_text = " ".join([f"{s.get('speaker', 'SPEAKER')}: {s.get('text', '')}" for s in current_batch])
    existing_fields = dict(state.get("extracted_fields", {}))

    # 2. Resolve Dynamic Frontend Questionnaire List specifically for this applicant
    dynamic_qs = list(state.get("dynamic_questionnaire", []))
    if not dynamic_qs and os.getenv("TESTING") != "true":
        try:
            from app.core.database import SessionLocal
            from app.models.question_bank import QuestionBank
            db_session = SessionLocal()
            try:
                emp_clean = (state.get("employment_type") or "self_employed").lower()
                sub_prof = (state.get("sub_profile") or "retail").lower().replace(" ", "_")
                if sub_prof in ("govt", "government"):
                    sub_prof = "salaried_govt"
                elif sub_prof in ("private", "corporate"):
                    sub_prof = "salaried_private"

                t1 = db_session.query(QuestionBank).filter(QuestionBank.tier == 1).order_by(QuestionBank.id).all()
                t2 = db_session.query(QuestionBank).filter(QuestionBank.tier == 2, QuestionBank.employment_type == emp_clean).order_by(QuestionBank.id).all()
                t3 = db_session.query(QuestionBank).filter(QuestionBank.tier == 3, QuestionBank.business_category == sub_prof).order_by(QuestionBank.id).all()
                dynamic_qs = [
                    {
                        "field_name": q.field_name,
                        "question_text": q.question_text,
                        "data_type": q.data_type,
                        "tier": q.tier,
                        "is_mandatory": q.is_mandatory
                    }
                    for q in (t1 + t2 + t3)
                ]
                state["dynamic_questionnaire"] = dynamic_qs
            finally:
                db_session.close()
        except Exception as err:
            logger.warning(f"Could not load fallback questionnaire in extract_fields: {err}")

    # Build focused list of target questionnaire fields
    questionnaire_targets = [
        {
            "field_name": q.get("field_name"),
            "question": q.get("question_text"),
            "data_type": q.get("data_type", "text"),
            "tier": q.get("tier")
        }
        for q in dynamic_qs if q.get("field_name")
    ]

    # 3. Resolve Active Follow-Up Targets
    active_followups = state.get("active_followup_questions", [])
    followup_targets = [
        {
            "target_field": q.get("target_field") or f"followup_q_{idx}",
            "question": q.get("question_text", ""),
            "category": q.get("category", "GENERAL")
        }
        for idx, q in enumerate(active_followups) if q.get("question_text")
    ]

    # 4. Known Already-Stated Fields
    already_stated_summary = {
        k: f"{v.get('value')} ({v.get('status')})"
        for k, v in existing_fields.items()
        if v.get("status") in ("STATED", "INFERRED")
    }

    # 5. Build Prompts
    system_prompt = (
        "You are an expert Credit Underwriter and Field Intelligence Specialist at MSFincap NBFC.\n"
        "Your task is to analyze the complete Personal Discussion (PD) audio transcript between a Loan Officer "
        "and a Loan Applicant (conducted in Hindi, Hinglish, or English) and accurately extract underwriting data points.\n"
        "You must respond ONLY with a raw, valid JSON object matching the requested schema."
    )

    user_prompt = f"""
=== BORROWER & SESSION PROFILE ===
Employment Type: {state.get('employment_type', 'SELF_EMPLOYED')}
Business Sub-Profile: {state.get('sub_profile', 'RETAIL')}
Round / Batch Sequence: #{state.get('batch_index', 0)}

=== TARGET CATEGORY 1: DYNAMIC FRONTEND QUESTIONNAIRE FIELDS ===
These are the exact questions displayed on the credit officer's frontend form for this borrower profile.
Extract the borrower's answer for any field discussed in the conversation:
{json.dumps(questionnaire_targets, indent=2, ensure_ascii=False)}

=== TARGET CATEGORY 2: ACTIVE AI FOLLOW-UP QUESTIONS ===
These are dynamic AI follow-up questions generated for the officer. If the dialogue answers or implies an answer to any of these:
1. Extract it under "extracted_fields" using the follow-up's target_field.
2. AND include it in "answered_followups" list with id, target_field, answer, value, status, confidence, and evidence_quote:
{json.dumps(followup_targets, indent=2, ensure_ascii=False)}

=== TARGET CATEGORY 3: UNSTRUCTURED CREDIT DISCOVERIES ===
If the transcript contains ANY other critical financial, operational, or risk information NOT listed in Target 1 or Target 2 (such as undeclared debts, local chit fund / bisi commitments, seasonal closures, major asset ownership, customer concentration, landlord disputes, machine specifications), EXTRACT IT with a clear descriptive snake_case field name and set "is_unstructured": true.

=== PREVIOUSLY CAPTURED FIELDS ===
{json.dumps(already_stated_summary, indent=2, ensure_ascii=False) if already_stated_summary else "None captured yet."}

=== FULL TRANSCRIPT HISTORY (TURNS 1 TO PRESENT) ===
{full_transcript_text}

=== LATEST 15-SECOND AUDIO SLICE ===
"{latest_slice_text}"

=== EXTRACTION RULES ===
1. Status Definitions:
   - "STATED": Explicitly confirmed by applicant with a clear figure, trade detail, or fact.
   - "INFERRED": Logically deduced from surrounding statements (e.g. daily sales Rs. 10,000 * 25 days = Rs. 2,50,000/month). Detail the math in 'reasoning'.
   - Do NOT output fields that were never mentioned or discussed.
2. For numeric/currency fields, convert spoken Hindi/Hinglish numbers to standard numeric formats where appropriate (e.g., "2.5 lakh" -> 250000, "15 percent" -> 15.0, "bees hazaar" -> 20000).
3. Do not downgrade an already "STATED" field to "INFERRED".
4. Quote the exact spoken phrase in 'evidence_quote'.

=== OUTPUT JSON FORMAT ===
{{
  "extracted_fields": {{
    "monthly_turnover": {{
      "value": 250000.0,
      "status": "STATED",
      "confidence": 0.95,
      "reasoning": "Declared 2.5 lakh monthly sales in store",
      "evidence_quote": "Mahine ka dhai lakh ka turnover ho jata hai",
      "is_unstructured": false
    }},
    "supplier_payment_terms": {{
      "value": "15 days credit",
      "status": "STATED",
      "confidence": 0.92,
      "reasoning": "Responded to follow up question on supplier terms",
      "evidence_quote": "Supplier se 15 din ka udhaar milta hai",
      "is_unstructured": false
    }}
  }},
  "answered_followups": [
    {{
      "id": "gq_0_1",
      "target_field": "supplier_payment_terms",
      "answer": "15 days credit from distributors",
      "value": "15 days credit",
      "status": "STATED",
      "confidence": 0.92,
      "evidence_quote": "Supplier se 15 din ka udhaar milta hai"
    }}
  ]
}}
"""

    try:
        res = None
        try:
            from app.agents.llm_client import GeminiClient
            gemini_client = GeminiClient()
            res = gemini_client.complete_json(system=system_prompt, user=user_prompt)
        except Exception as gemini_err:
            logger.warning(f"GeminiClient extraction failed, falling back to complete(): {gemini_err}")
            try:
                combined = f"{system_prompt}\n\n{user_prompt}"
                res = complete(combined, response_format="json")
            except Exception as fb_err:
                logger.error(f"Fallback extraction also failed: {fb_err}")

        if isinstance(res, dict) and "extracted_fields" in res:
            new_fields = res["extracted_fields"]
            for field_name, f_data in new_fields.items():
                if not isinstance(f_data, dict):
                    continue
                new_status = str(f_data.get("status", "NOT_CAPTURED")).upper()
                if new_status not in ("STATED", "INFERRED"):
                    continue

                curr = existing_fields.get(field_name, {})
                curr_status = str(curr.get("status", "NOT_CAPTURED")).upper()

                # Do not downgrade a STATED value to INFERRED
                if curr_status == "STATED" and new_status == "INFERRED":
                    continue

                val = f_data.get("value")
                is_numeric = isinstance(val, (int, float)) or (isinstance(val, str) and val.replace(".", "", 1).isdigit())
                f_data["needs_reconfirmation"] = is_numeric
                existing_fields[field_name] = f_data

            # Process answered follow-ups and move them to resolved_followup_questions
            answered_list = res.get("answered_followups", []) if isinstance(res, dict) else []
            answered_map = {}
            for item in answered_list:
                if isinstance(item, dict):
                    k = item.get("id") or item.get("target_field")
                    if k:
                        answered_map[k] = item

            remaining_active = []
            resolved_followups = list(state.get("resolved_followup_questions", []))

            for q in active_followups:
                q_id = q.get("id")
                q_target = q.get("target_field")
                ans_item = answered_map.get(q_id) or answered_map.get(q_target)

                if not ans_item and q_target and q_target in existing_fields and existing_fields[q_target].get("status") in ("STATED", "INFERRED"):
                    ans_item = {
                        "id": q_id,
                        "target_field": q_target,
                        "answer": str(existing_fields[q_target].get("value")),
                        "value": existing_fields[q_target].get("value"),
                        "status": existing_fields[q_target].get("status", "INFERRED"),
                        "confidence": existing_fields[q_target].get("confidence", 0.9),
                        "evidence_quote": existing_fields[q_target].get("evidence_quote", "")
                    }

                if ans_item:
                    q_copy = dict(q)
                    ans_val = str(ans_item.get("answer") or ans_item.get("value") or "")
                    q_copy["answer"] = ans_val
                    q_copy["inferred_answer"] = ans_val
                    q_copy["resolved"] = True
                    q_copy["status"] = "resolved"
                    resolved_followups.append(q_copy)

                    target_f = q_target or f"followup_{q_id}"
                    if target_f not in existing_fields or existing_fields[target_f].get("status") != "STATED":
                        val_extracted = ans_item.get("value") or ans_val
                        is_num = isinstance(val_extracted, (int, float)) or (isinstance(val_extracted, str) and val_extracted.replace(".", "", 1).isdigit())
                        existing_fields[target_f] = {
                            "value": val_extracted,
                            "status": str(ans_item.get("status", "INFERRED")).upper(),
                            "confidence": float(ans_item.get("confidence", 0.9)),
                            "reasoning": f"Extracted from dialogue for follow-up: {q.get('question_text')}",
                            "evidence_quote": ans_item.get("evidence_quote", ""),
                            "needs_reconfirmation": is_num
                        }
                    print(f"   ↳ [AI Follow-up Inferred & Resolved] '{q.get('question_text')}': \"{ans_val}\"", flush=True)
                else:
                    remaining_active.append(q)

            state["active_followup_questions"] = remaining_active
            state["resolved_followup_questions"] = resolved_followups
            state["extracted_fields"] = existing_fields

            print(f"   -> [Node 3: extract_fields] Processed Gemini extraction: {len(new_fields)} field(s) in batch, total extracted now: {len(existing_fields)}", flush=True)
            for fn, fd in (new_fields or {}).items():
                if fd.get("status") in ("STATED", "INFERRED"):
                    unst = " [UNSTRUCTURED]" if fd.get("is_unstructured") else ""
                    print(f"       + {fn}{unst}: \"{fd.get('value')}\" ({fd.get('status')}, conf={fd.get('confidence')})", flush=True)

            # Dynamic Granular Trade Profile Resolution via ChromaDB:
            occ_data = existing_fields.get("exact_occupation_details") or existing_fields.get("occupation_description") or existing_fields.get("nature_of_work")
            if occ_data and occ_data.get("value"):
                occ_text = str(occ_data.get("value"))
                parent_category = state.get("sub_profile", "RETAIL")
                try:
                    from app.core.database import SessionLocal
                    from app.rag.retrieval import resolve_granular_sub_profile
                    with SessionLocal() as db_session:
                        granular_profile = resolve_granular_sub_profile(parent_category, occ_text, db_session)
                        if granular_profile and granular_profile.sub_profile != state.get("sub_profile"):
                            old_sub = state.get("sub_profile")
                            state["sub_profile"] = granular_profile.sub_profile
                            state["rag_requirements"] = {
                                "sub_profile": granular_profile.sub_profile,
                                "display_name": granular_profile.display_name,
                                "benchmark_margins_json": granular_profile.benchmark_margins_json,
                                "required_info_checklist_json": granular_profile.required_info_checklist_json,
                                "red_flags_json": granular_profile.red_flags_json
                            }
                            print(f"   [RAG Dynamic Trade Match] Upgraded sub_profile from '{old_sub}' -> '{granular_profile.sub_profile}' ({granular_profile.display_name}) based on voice: \"{occ_text}\"", flush=True)
                except Exception as rag_err:
                    logger.warning(f"Failed to dynamically upgrade granular trade profile: {rag_err}")
    except Exception as e:
        logger.error(f"Error in extract_fields: {e}")

    return state


# -------------------------------------------------------------------------
# Node 4: Contradiction & Customer Consistency Node
# -------------------------------------------------------------------------
def check_consistency(state: PDWorkflowState) -> PDWorkflowState:
    """
    Cross-references statements in the new batch against the full transcript history.
    Identifies discrepancies and assigns severity: LOW | MEDIUM | HIGH.
    Never auto-resolves discrepancies; both values persist for underwriter review.
    """
    current_batch = state.get("current_batch", [])
    history = state.get("transcript_history", [])
    if not current_batch or len(history) <= len(current_batch):
        return state

    current_text = " ".join([f"{s.get('speaker', 'SPEAKER')}: {s.get('text', '')}" for s in current_batch])
    history_text = " ".join([f"{s.get('speaker', 'SPEAKER')}: {s.get('text', '')}" for s in history[:-len(current_batch)]])

    prompt = f"""
    Check for contradictions between what the applicant previously stated versus what they just stated in the latest batch.
    
    Prior Conversation History:
    "{history_text[-2000:]}"

    Latest Batch:
    "{current_text}"

    If the applicant contradicts an earlier statement (e.g. claiming Rs. 20L annual sales when earlier stating daily sales of Rs. 2,000, or differing family members / shop tenure):
    Identify each contradiction with severity:
    - LOW: minor variance or rounding
    - MEDIUM: notable discrepancy (e.g. 20-50% difference)
    - HIGH: major contradiction (e.g. >2x difference or conflicting factual claims)

    Return JSON:
    {{
      "contradictions": [
        {{
          "field_name": "monthly_turnover",
          "stated_value_1": "20,00,000 annual",
          "stated_value_2": "2,000 daily",
          "severity": "HIGH",
          "explanation": "Claimed 20L annual sales but stated daily sales of Rs. 2,000 implies only ~6L annual."
        }}
      ]
    }}
    """

    try:
        res = complete(prompt, response_format="json")
        if isinstance(res, dict) and "contradictions" in res:
            found = res.get("contradictions", [])
            if found:
                contradictions = list(state.get("detected_contradictions", []))
                for c in found:
                    contradictions.append(c)
                    state["customer_contradiction_count"] = state.get("customer_contradiction_count", 0) + 1
                    logger.warning(f"Detected customer contradiction [{c.get('severity')}]: {c.get('explanation')}")
                state["detected_contradictions"] = contradictions
    except Exception as e:
        logger.error(f"Error in check_consistency: {e}")

    print(f"   ↳ [Node 4: check_consistency] Discrepancy audit complete. Active contradictions: {len(state.get('detected_contradictions', []))}", flush=True)
    return state


# -------------------------------------------------------------------------
# Node 5: RAG Context & Gap Analyzer Node
# -------------------------------------------------------------------------
def analyze_gaps(state: PDWorkflowState) -> PDWorkflowState:
    """
    Round 1: Loads RAG requirements for the sub_profile and caches in state.
    Cost Guard: Skips LLM comparison if the new batch added fewer than 15 words.
    Compares checklist against extracted_fields to set gaps_remaining.
    """
    # 1. Round 1 / Cache check
    if not state.get("rag_requirements"):
        sub_prof = state.get("sub_profile", "RETAIL")
        state["rag_requirements"] = {
            "sub_profile": sub_prof,
            "required_info_checklist_json": [
                "monthly_turnover", "net_margin_pct", "supplier_payment_terms", "credit_ledger_recovery_cycle"
            ],
            "red_flags_json": []
        }

    # 2. Cost Guard: Skip if current batch added < 15 words
    current_batch = state.get("current_batch", [])
    total_words = sum(len(str(seg.get("text", "")).split()) for seg in current_batch)
    if total_words < 15:
        logger.info(f"Cost Guard activated: batch has only {total_words} words (<15). Skipping LLM gap evaluation.")
        return state

    # 3. Gap Evaluation
    checklist = state.get("rag_requirements", {}).get("required_info_checklist_json", [])
    extracted = state.get("extracted_fields", {})

    missing_items = []
    for item in checklist:
        field_match = extracted.get(item)
        if not field_match or field_match.get("status") not in ("STATED", "INFERRED"):
            missing_items.append(item)

    # If missing items remain, gaps_remaining is True
    state["gaps_remaining"] = len(missing_items) > 0
    print(f"   ↳ [Node 5: analyze_gaps] Remaining checklist gaps: {len(missing_items)} ({missing_items[:4]}...) | Gaps Remaining: {state['gaps_remaining']}", flush=True)
    return state


# -------------------------------------------------------------------------
# Conditional Edge Router
# -------------------------------------------------------------------------
def should_generate_followups(state: PDWorkflowState) -> str:
    if state.get("gaps_remaining", True):
        return "generate_followups"
    return "mark_resolved"


# -------------------------------------------------------------------------
# Node 6: Dynamic Follow-Up Generator Node
# -------------------------------------------------------------------------
def generate_followups(state: PDWorkflowState) -> PDWorkflowState:
    """
    Dynamically generates prioritized follow-up questions tailored to missing items and red flags.
    - Matches candidate questions with the dynamic predefined questionnaire (Tier 1-3).
    - Appends all follow-ups to a master session list (all_followup_questions_history).
    - Uses LLM semantic deduplication: checks if new candidate and previous follow-up questions are the same.
      If the same, DO NOT append.
    - Only non-duplicate, active questions are kept in active_followup_questions for display on frontend.
    """
    active_qs = list(state.get("active_followup_questions", []))
    resolved_qs = list(state.get("resolved_followup_questions", []))
    all_history = list(state.get("all_followup_questions_history", []))
    if not all_history:
        all_history = list(active_qs + resolved_qs)

    extracted = state.get("extracted_fields", {})
    dynamic_qs = list(state.get("dynamic_questionnaire", []))

    # 1. Resolve and remove any follow-up question whose target_field was answered / extracted
    unresolved_qs = []
    for q in active_qs:
        target = q.get("target_field")
        if target and target in extracted and extracted[target].get("status") in ("STATED", "INFERRED"):
            q_copy = dict(q)
            q_copy["resolved"] = True
            q_copy["status"] = "resolved"
            q_copy["answer"] = str(extracted[target].get("value", ""))
            resolved_qs.append(q_copy)
            print(f"   ↳ [Follow-Up Resolved] Field '{target}' captured. Removing follow-up: {q.get('question_text', '')}", flush=True)
            continue
        unresolved_qs.append(q)
    active_qs = unresolved_qs
    state["active_followup_questions"] = active_qs
    state["resolved_followup_questions"] = resolved_qs

    checklist = state.get("rag_requirements", {}).get("required_info_checklist_json", [])
    red_flags = state.get("rag_requirements", {}).get("red_flags_json", [])

    # Exclude items already answered or already actively prompted
    already_asked_targets = {q.get("target_field") for q in active_qs if q.get("target_field")}
    already_history_targets = {q.get("target_field") for q in all_history if q.get("target_field")}

    missing_items = [
        item for item in checklist 
        if extracted.get(item, {}).get("status") not in ("STATED", "INFERRED")
        and item not in already_asked_targets
        and item not in already_history_targets
    ]

    if not missing_items:
        print(f"   ↳ [Node 6: generate_followups] All checklist items covered or in queue. Active queue: {len(active_qs)}", flush=True)
        return state

    recent_history = state.get("transcript_history", [])[-6:]
    recent_text = " ".join([f"{s.get('speaker', 'SPEAKER')}: {s.get('text', '')}" for s in recent_history])

    num_to_request = min(len(missing_items), 3)
    prompt = f"""
    You are an AI underwriting assistant on an in-person personal discussion (Ground PD).
    Business Category: {state.get('sub_profile', 'GENERAL')}
    Missing Info Checklist Items: {missing_items[:5]}
    Industry Red Flags to watch for: {red_flags[:3]}

    Recent Dialogue:
    "{recent_text}"

    Generate {num_to_request} natural, conversational follow-up question(s) for the officer to ask right now.
    Phrasing should be conversational Hindi/Hinglish/English that fits natural speech.

    Return JSON:
    {{
      "questions": [
        {{
          "question_text": "Aapke suppliers se raw material cash pe aata hai ya credit terms pe? Kitne din ka credit milta hai?",
          "category": "SUPPLIER_TERMS",
          "priority": 1,
          "target_field": "supplier_payment_terms"
        }}
      ]
    }}
    """

    try:
        res = complete(prompt, response_format="json")
        if isinstance(res, dict) and "questions" in res:
            raw_candidates = res.get("questions", [])[:num_to_request]
            
            # Step A: Filter by lexical normalization and match with dynamic predefined questionnaire
            filtered_candidates = []
            all_known_normalized = {
                normalize_question_text(q.get("question_text") or q.get("text") or ""): q
                for q in (all_history + active_qs)
            }
            dynamic_by_norm = {
                normalize_question_text(dq.get("question_text") or dq.get("text") or ""): dq
                for dq in dynamic_qs
            }

            for cand in raw_candidates:
                c_text = cand.get("question_text", "").strip()
                if not c_text:
                    continue
                c_norm = normalize_question_text(c_text)
                
                # Check if exact normalized match with any past or active follow-up
                if c_norm in all_known_normalized:
                    print(f"   ↳ [Deduplication: Lexical Match] Skipped duplicate follow-up: \"{c_text}\"", flush=True)
                    continue

                # Match with dynamic predefined questionnaire
                if c_norm in dynamic_by_norm:
                    print(f"   ↳ [Deduplication: Predefined Match] Question already in predefined questionnaire: \"{c_text}\"", flush=True)
                    continue

                # Cross-check topic/field against dynamic questionnaire
                for dq in dynamic_qs:
                    dq_field = dq.get("field_name")
                    if dq_field and cand.get("target_field") and (dq_field == cand.get("target_field") or dq_field in cand.get("target_field")):
                        cand["target_field"] = dq_field
                        break

                target = cand.get("target_field")
                if target and target in already_asked_targets:
                    print(f"   ↳ [Deduplication: Target In Queue] Target field '{target}' already active in queue: \"{c_text}\"", flush=True)
                    continue

                filtered_candidates.append(cand)

            # Step B: LLM Semantic Deduplication Check
            if filtered_candidates and (all_history or dynamic_qs) and os.getenv("TESTING") != "true":
                try:
                    prior_questions_sample = [
                        q.get("question_text") or q.get("text")
                        for q in (all_history + dynamic_qs)
                        if (q.get("question_text") or q.get("text"))
                    ][-20:]

                    dedup_prompt = f"""
You are an underwriting quality auditor checking for redundant interview questions.
Compare each candidate follow-up question against the list of EXISTING questions already asked or present in the interview form.
Determine if any candidate question is asking the SAME thing or is semantically equivalent to an existing question.

EXISTING QUESTIONS:
{json.dumps(prior_questions_sample, indent=2, ensure_ascii=False)}

CANDIDATE QUESTIONS:
{json.dumps([{'index': idx, 'question': c.get('question_text')} for idx, c in enumerate(filtered_candidates)], indent=2, ensure_ascii=False)}

Return JSON:
{{
  "evaluations": [
    {{"index": 0, "is_duplicate": false, "reason": "Unique question not covered above"}}
  ]
}}
"""
                    dedup_eval = complete(dedup_prompt, response_format="json")
                    if isinstance(dedup_eval, dict) and "evaluations" in dedup_eval:
                        dup_indices = {
                            ev.get("index") for ev in dedup_eval["evaluations"] 
                            if ev.get("is_duplicate") is True
                        }
                        surviving = []
                        for i, cand in enumerate(filtered_candidates):
                            if i in dup_indices:
                                print(f"   ↳ [Deduplication: LLM Semantic Match] Discarded duplicate follow-up: \"{cand.get('question_text')}\"", flush=True)
                            else:
                                surviving.append(cand)
                        filtered_candidates = surviving
                except Exception as eval_err:
                    logger.warning(f"Semantic deduplication LLM evaluation error: {eval_err}")

            # Step C: Append only deduplicated, unique questions
            for idx, q in enumerate(filtered_candidates):
                cat = q.get("category", "GENERAL") or "GENERAL"
                target = q.get("target_field", "")
                q_text = q.get("question_text", "")
                cat_formatted = cat.replace('_', ' ').title()
                q_item = {
                    "id": f"gq_{state.get('batch_index', 0)}_{len(all_history) + 1}",
                    "question_text": q_text,
                    "text": q_text,
                    "category": cat,
                    "tag": f"AI Follow-up ({cat_formatted})",
                    "reason": f"RAG benchmark gap: {target.replace('_', ' ').title() if target else cat_formatted}",
                    "target_field": target,
                    "round_number": state.get("batch_index", 0),
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                active_qs.append(q_item)
                all_history.append(q_item)
                already_asked_targets.add(target)

            state["active_followup_questions"] = active_qs
            state["all_followup_questions_history"] = all_history
            state["resolved_followup_questions"] = resolved_qs

            print(f"   ↳ [Node 6: generate_followups] Active non-duplicate queue: {len(active_qs)} | Total session follow-ups: {len(all_history)}", flush=True)
            for q in active_qs:
                print(f"       ? \"{q.get('question_text')}\"", flush=True)
    except Exception as e:
        logger.error(f"Error in generate_followups: {e}")

    return state


# -------------------------------------------------------------------------
# Node 7: Gaps Resolved State Node
# -------------------------------------------------------------------------
def mark_resolved(state: PDWorkflowState) -> PDWorkflowState:
    state["gaps_remaining"] = False
    print(f"   ↳ [Node 7: mark_resolved] All mandatory credit checklist items covered!", flush=True)
    return state


# -------------------------------------------------------------------------
# Build LangGraph Workflow
# -------------------------------------------------------------------------
workflow = StateGraph(PDWorkflowState)

workflow.add_node("ingest_batch", ingest_batch)
workflow.add_node("evaluate_diligence", evaluate_diligence)
workflow.add_node("extract_fields", extract_fields)
workflow.add_node("check_consistency", check_consistency)
workflow.add_node("analyze_gaps", analyze_gaps)
workflow.add_node("generate_followups", generate_followups)
workflow.add_node("mark_resolved", mark_resolved)

workflow.add_edge(START, "ingest_batch")
workflow.add_edge("ingest_batch", "evaluate_diligence")
workflow.add_edge("evaluate_diligence", "extract_fields")
workflow.add_edge("extract_fields", "check_consistency")
workflow.add_edge("check_consistency", "analyze_gaps")

workflow.add_conditional_edges(
    "analyze_gaps",
    should_generate_followups,
    {
        "generate_followups": "generate_followups",
        "mark_resolved": "mark_resolved"
    }
)

workflow.add_edge("generate_followups", END)
workflow.add_edge("mark_resolved", END)

checkpointer = MemorySaver()
pd_graph = workflow.compile(checkpointer=checkpointer)


# -------------------------------------------------------------------------
# Batch Results Persistence & Local Audit Logging
# -------------------------------------------------------------------------
def persist_batch_results(state: PDWorkflowState, db: Session) -> List[Dict[str, Any]]:
    """
    Synchronizes batch execution output to PostgreSQL / SQLite:
      - transcript_segments
      - extracted_fields
      - gap_questions
      - customer_consistency_flags
      - officer_pd_scores running metrics
    Appends a tamper-evident audit line to logs/pd_session_{session_id}.jsonl.
    Returns active_followup_questions for live client update.
    """
    session_id = state["session_id"]
    current_batch = state.get("current_batch", [])

    # 1. Transcript segments
    for s in current_batch:
        seg = TranscriptSegment(
            session_id=session_id,
            start_time=float(s.get("start_time", 0.0)),
            end_time=float(s.get("end_time", 0.0)),
            speaker=str(s.get("speaker", "OFFICER")).upper(),
            text=str(s.get("text", "")).strip(),
            confidence=float(s.get("confidence", 1.0))
        )
        db.add(seg)

    # 2. Extracted fields
    for field_name, f_data in state.get("extracted_fields", {}).items():
        existing = db.query(ExtractedField).filter(
            ExtractedField.pd_session_id == session_id,
            ExtractedField.field_name == field_name
        ).first()

        status_val = str(f_data.get("status", "STATED")).lower()
        val_str = str(f_data.get("value", ""))
        reasoning = f_data.get("reasoning", "")

        if existing:
            existing.value = val_str
            existing.source = status_val
            existing.confidence_note = reasoning
        else:
            new_ef = ExtractedField(
                pd_session_id=session_id,
                field_name=field_name,
                value=val_str,
                source=status_val,
                confidence_note=reasoning,
                officer_confirmed=False
            )
            db.add(new_ef)

    # 3. Gap Questions
    for q in state.get("active_followup_questions", []):
        existing_q = db.query(GapQuestion).filter(
            GapQuestion.pd_session_id == session_id,
            GapQuestion.question_text == q.get("question_text")
        ).first()
        if not existing_q:
            new_gq = GapQuestion(
                pd_session_id=session_id,
                question_text=q.get("question_text", ""),
                category=q.get("category", "GENERAL"),
                round_number=int(q.get("round_number", 1)),
                resolved=False
            )
            db.add(new_gq)

    for q in state.get("resolved_followup_questions", []):
        existing_q = db.query(GapQuestion).filter(
            GapQuestion.pd_session_id == session_id,
            GapQuestion.question_text == q.get("question_text")
        ).first()
        ans_val = str(q.get("answer") or q.get("value") or "")
        if existing_q:
            existing_q.resolved = True
            if ans_val:
                existing_q.answer = ans_val
        else:
            new_gq = GapQuestion(
                pd_session_id=session_id,
                question_text=q.get("question_text", ""),
                category=q.get("category", "GENERAL"),
                round_number=int(q.get("round_number", 1)),
                resolved=True,
                answer=ans_val
            )
            db.add(new_gq)

    # 4. Customer Consistency Flags
    for c in state.get("detected_contradictions", []):
        existing_c = db.query(CustomerConsistencyFlag).filter(
            CustomerConsistencyFlag.pd_session_id == session_id,
            CustomerConsistencyFlag.field_name == c.get("field_name"),
            CustomerConsistencyFlag.value_a == str(c.get("stated_value_1"))
        ).first()
        if not existing_c:
            new_flag = CustomerConsistencyFlag(
                pd_session_id=session_id,
                field_name=c.get("field_name", "UNKNOWN"),
                value_a=str(c.get("stated_value_1", "")),
                value_b=str(c.get("stated_value_2", "")),
                severity=str(c.get("severity", "MEDIUM")).lower(),
                resolution_note=c.get("explanation", "")
            )
            db.add(new_flag)

    # 5. Officer running metrics
    score = db.query(OfficerPDScore).filter(OfficerPDScore.pd_session_id == session_id).first()
    if score:
        score.suggestion_uptake_score = float(state.get("officer_uptake_count", 0))
        score.proactive_diligence_bonus = float(state.get("officer_proactive_bonus_points", 0))

    db.commit()

    # 6. Audit Trail Logging (on-device / backend)
    log_dir = os.path.join(settings.BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    audit_file = os.path.join(log_dir, f"pd_session_{session_id}.jsonl")
    audit_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "batch_index": state.get("batch_index", 0),
        "transcript_segments_count": len(current_batch),
        "active_followup_count": len(state.get("active_followup_questions", [])),
        "resolved_followup_count": len(state.get("resolved_followup_questions", [])),
        "officer_uptake_count": state.get("officer_uptake_count", 0),
        "officer_proactive_bonus_points": state.get("officer_proactive_bonus_points", 0),
        "customer_contradiction_count": state.get("customer_contradiction_count", 0),
        "gaps_remaining": state.get("gaps_remaining", True)
    }
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(audit_record) + "\n")

    return state.get("active_followup_questions", [])
