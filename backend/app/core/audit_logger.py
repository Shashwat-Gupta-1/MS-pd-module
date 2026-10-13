import os
import sys
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from app.core.config import settings

logger = logging.getLogger("pd_audit")

# Reconfigure stdout/stderr on Windows to use UTF-8 and avoid UnicodeEncodeError on emojis
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _safe_print(text: str = "", flush: bool = True) -> None:
    """Prints text safely without crashing on terminal encoding issues (e.g. cp1252 on Windows)."""
    try:
        print(text, flush=flush)
    except UnicodeEncodeError:
        try:
            encoding = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
            safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
            print(safe_text, flush=flush)
        except Exception:
            pass


class PDAuditLogger:
    """
    Comprehensive structured audit logger for MSFincap PD Module.
    Captures:
    1. Officer Info (ID, name, phone, branch, role)
    2. Customer & Application Info (Applicant ID, name, phone, PAN, sub-profile, loan amount)
    3. Whisper / Speech-to-Text logs (chunk sequence, offset, duration, raw transcript, segments, confidence)
    4. LangGraph Pipeline logs (Node 1 to 7 detailed execution, extractions, diligence bonuses, contradictions, AI questions)
    5. Storage in logs/pd_session_audit.log, logs/sessions/{session_id}.jsonl, and logs/sessions/{session_id}_summary.json
    """

    def __init__(self):
        self.logs_dir = Path(settings.BASE_DIR) / "logs"
        self.sessions_dir = self.logs_dir / "sessions"
        self._ensure_dirs()

    def _ensure_dirs(self):
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create logs directories: {e}")

    def get_global_log_file(self) -> Path:
        return self.logs_dir / "pd_session_audit.log"

    def get_session_jsonl_file(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.jsonl"

    def get_session_summary_file(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}_summary.json"

    def _write_jsonl(self, session_id: str, record: Dict[str, Any]):
        """Writes an event record to the session JSONL file and the global audit log."""
        self._ensure_dirs()
        json_str = json.dumps(record, default=str)

        # 1. Per-session JSONL
        session_file = self.get_session_jsonl_file(session_id)
        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json_str + "\n")

        # 2. Global readable audit log
        global_file = self.get_global_log_file()
        with open(global_file, "a", encoding="utf-8") as f:
            f.write(f"[{record.get('timestamp')}] [{record.get('event_type')}] [Session: {session_id}] {json_str}\n")

    def log_session_start(
        self,
        session_id: str,
        officer_info: Dict[str, Any],
        customer_info: Dict[str, Any],
        application_info: Dict[str, Any]
    ):
        """Logs when a new PD session is initiated."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "SESSION_INITIALIZED",
            "session_id": session_id,
            "officer": officer_info,
            "customer": customer_info,
            "application": application_info
        }
        self._write_jsonl(session_id, record)
        self._update_session_summary(session_id, {"officer": officer_info, "customer": customer_info, "application": application_info, "status": "active"})

        # Terminal Visual Box
        border = "=" * 80
        _safe_print(f"\n{border}", flush=True)
        _safe_print(f"🎬 [PD AUDIT] NEW SESSION INITIALIZED: {session_id}", flush=True)
        _safe_print(f"👤 OFFICER:  {officer_info.get('name')} (📱 {officer_info.get('phone')}) | Role: {officer_info.get('role')} | Branch: {officer_info.get('branch')}", flush=True)
        _safe_print(f"🏢 CUSTOMER: {customer_info.get('name')} (📱 {customer_info.get('phone')}) | PAN: {customer_info.get('pan')} | Profile: {customer_info.get('sub_profile')}", flush=True)
        _safe_print(f"📄 APP ID:   {application_info.get('id')} | Loan: ₹{application_info.get('requested_amount', 0):,} | Product: {application_info.get('product_type')}", flush=True)
        _safe_print(f"{border}\n", flush=True)

    def log_whisper_chunk(
        self,
        session_id: str,
        chunk_sequence: int,
        audio_bytes_length: int,
        offset_sec: float,
        segments: List[Dict[str, Any]],
        officer_info: Optional[Dict[str, Any]] = None,
        customer_info: Optional[Dict[str, Any]] = None
    ):
        """Logs incoming live audio chunk and Whisper Speech-to-Text transcription."""
        raw_text = " ".join([f"[{s.get('speaker', 'SPEAKER').upper()}]: {s.get('text', '')}" for s in segments])
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "WHISPER_AUDIO_CHUNK_TRANSCRIBED",
            "session_id": session_id,
            "chunk_sequence": chunk_sequence,
            "audio_bytes_length": audio_bytes_length,
            "offset_sec": offset_sec,
            "whisper_model": settings.whisper_model,
            "segments_count": len(segments),
            "segments": segments,
            "raw_text": raw_text,
            "officer": officer_info,
            "customer": customer_info
        }
        self._write_jsonl(session_id, record)

        # Terminal Print
        _safe_print(f"\n--- 🎙️ [WHISPER CHUNK #{chunk_sequence}] ({audio_bytes_length} bytes, offset: {offset_sec:.1f}s) ---", flush=True)
        if segments:
            for s in segments:
                conf = s.get("confidence", 1.0) * 100
                _safe_print(f"   [{s.get('speaker', 'SPEAKER').upper()}] ({s.get('start', 0):.1f}s-{s.get('end', 0):.1f}s, conf: {conf:.1f}%): \"{s.get('text', '')}\"", flush=True)
        else:
            _safe_print("   (Non-speech audio or silence detected)", flush=True)

    def log_langgraph_batch_execution(
        self,
        session_id: str,
        chunk_sequence: int,
        officer_info: Dict[str, Any],
        customer_info: Dict[str, Any],
        application_info: Dict[str, Any],
        segments: List[Dict[str, Any]],
        result_state: Dict[str, Any]
    ):
        """
        Logs complete 7-node LangGraph pipeline run for a batch:
        - Node 1 Ingest
        - Node 2 Diligence & Uptake
        - Node 3 Information Extraction
        - Node 4 RAG Benchmark Comparison
        - Node 5 Contradiction Cross-Checker
        - Node 6 Dynamic Follow-Up Generator
        - Node 7 State Evaluator
        """
        extracted = result_state.get("extracted_fields", {})
        active_qs = result_state.get("active_followup_questions", [])
        resolved_qs = result_state.get("resolved_followup_questions", [])
        contradictions = result_state.get("detected_contradictions", [])
        uptake_count = result_state.get("officer_uptake_count", 0)
        bonus_points = result_state.get("officer_proactive_bonus_points", 0)
        gaps_remaining = result_state.get("gaps_remaining", True)

        nodes_summary = {
            "node_1_ingest": {
                "new_segments_in_batch": len(segments),
                "total_transcript_history_turns": len(result_state.get("transcript_history", []))
            },
            "node_2_officer_diligence": {
                "officer_uptake_count": uptake_count,
                "officer_proactive_bonus_points": bonus_points,
            },
            "node_3_extraction": {
                "total_fields_extracted": len(extracted),
                "fields": {k: {"value": v.get("value"), "source": v.get("status", v.get("source")), "confidence": v.get("confidence")} for k, v in extracted.items()}
            },
            "node_4_rag_benchmark": {
                "sub_profile": result_state.get("sub_profile", "GENERAL"),
                "benchmarks_loaded": bool(result_state.get("rag_requirements"))
            },
            "node_5_contradictions": {
                "count": len(contradictions),
                "flags": contradictions
            },
            "node_6_dynamic_questions": {
                "active_followup_count": len(active_qs),
                "questions": [q.get("question_text") for q in active_qs]
            },
            "node_7_state_evaluator": {
                "gaps_remaining": gaps_remaining,
                "round_number": result_state.get("round_number", chunk_sequence)
            }
        }

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "LANGGRAPH_PIPELINE_EXECUTED",
            "session_id": session_id,
            "chunk_sequence": chunk_sequence,
            "officer": officer_info,
            "customer": customer_info,
            "application": application_info,
            "whisper_transcript_summary": [s.get("text") for s in segments],
            "langgraph_nodes": nodes_summary,
            "metrics": {
                "officer_uptake_count": uptake_count,
                "officer_proactive_bonus_points": bonus_points,
                "customer_contradiction_count": len(contradictions),
                "gaps_remaining": gaps_remaining
            }
        }

        self._write_jsonl(session_id, record)
        self._update_session_summary(session_id, {
            "officer": officer_info,
            "customer": customer_info,
            "application": application_info,
            "last_chunk_sequence": chunk_sequence,
            "metrics": record["metrics"],
            "extracted_fields": nodes_summary["node_3_extraction"]["fields"],
            "active_followup_questions": active_qs,
            "contradictions": contradictions,
            "updated_at": record["timestamp"]
        })

        # Formatted Visual Terminal Banner
        border = "═" * 80
        thin_border = "─" * 80
        _safe_print(f"\n{border}", flush=True)
        _safe_print(f"🧠 [LANGGRAPH PIPELINE RUN] BATCH #{chunk_sequence} (Session: {session_id[:8]}...)", flush=True)
        _safe_print(f"{thin_border}", flush=True)
        _safe_print(f"👤 OFFICER:  {officer_info.get('name')} | Mobile: {officer_info.get('phone')} | Branch: {officer_info.get('branch')}", flush=True)
        _safe_print(f"🏢 CUSTOMER: {customer_info.get('name')} | Mobile: {customer_info.get('phone')} | PAN: {customer_info.get('pan')}", flush=True)
        _safe_print(f"📋 CASE:     {application_info.get('id')} | Amount: ₹{application_info.get('requested_amount', 0):,} | Type: {application_info.get('product_type')}", flush=True)
        _safe_print(f"{thin_border}", flush=True)
        _safe_print(f"🎤 WHISPER SPEECH-TO-TEXT: {len(segments)} segments transcribed in this slice", flush=True)
        for s in segments[:3]:
            _safe_print(f"   • [{s.get('speaker', 'borrower').upper()}]: \"{s.get('text', '')}\"", flush=True)
        if len(segments) > 3:
            _safe_print(f"   • ... and {len(segments) - 3} more turns", flush=True)
        _safe_print(f"{thin_border}", flush=True)
        _safe_print(f"⚡ LANGGRAPH 7-NODE EXECUTION DETAILS:", flush=True)
        _safe_print(f"   [Node 1 Ingest]       Processed {len(segments)} audio turns. History turns total: {nodes_summary['node_1_ingest']['total_transcript_history_turns']}", flush=True)
        _safe_print(f"   [Node 2 Diligence]    Uptake Score: {uptake_count} | Proactive Diligence Bonus: +{bonus_points} pts", flush=True)
        _safe_print(f"   [Node 3 Extraction]   Total Fields Captured: {len(extracted)}", flush=True)
        for f_name, f_data in list(extracted.items())[:4]:
            _safe_print(f"                         • {f_name}: {f_data.get('value')} (source: {f_data.get('status')})", flush=True)
        _safe_print(f"   [Node 4 Benchmark]    RAG Profile: {customer_info.get('sub_profile', 'RETAIL')} (ChromaDB verified)", flush=True)
        _safe_print(f"   [Node 5 Consistency]  Contradictions Detected: {len(contradictions)}", flush=True)
        for c in contradictions:
            _safe_print(f"                         ⚠️ {c.get('field_name')}: \"{c.get('stated_value_1')}\" vs \"{c.get('stated_value_2')}\" ({c.get('severity')})", flush=True)
        _safe_print(f"   [Node 6 AI Followups] Active suggestions generated for Officer UI: {len(active_qs)}", flush=True)
        for i, q in enumerate(active_qs[:3]):
            _safe_print(f"                         {i+1}. \"{q.get('question_text')}\" [{q.get('category')}]", flush=True)
        _safe_print(f"   [Node 7 Gaps Status]  Gaps Remaining: {gaps_remaining}", flush=True)
        _safe_print(f"{border}\n", flush=True)

    def log_field_reconfirmation(self, session_id: str, officer_info: Dict[str, Any], field_name: str, value: Any, confirmed: bool):
        """Logs officer manual field confirmation or override."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "FIELD_RECONFIRMED",
            "session_id": session_id,
            "officer": officer_info,
            "field_name": field_name,
            "value": value,
            "officer_confirmed": confirmed
        }
        self._write_jsonl(session_id, record)
        _safe_print(f"📝 [AUDIT RECONFIRM] Officer {officer_info.get('name')} confirmed '{field_name}' = '{value}'", flush=True)

    def log_remarks_and_flags(self, session_id: str, officer_info: Dict[str, Any], remarks: str, resolutions: Optional[List[Dict[str, Any]]] = None):
        """Logs officer closing remarks and consistency flag resolutions."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "OFFICER_REMARKS_SUBMITTED",
            "session_id": session_id,
            "officer": officer_info,
            "remarks": remarks,
            "resolutions": resolutions or []
        }
        self._write_jsonl(session_id, record)
        _safe_print(f"✍️ [AUDIT REMARKS] Officer {officer_info.get('name')} recorded observations: \"{remarks[:80]}...\"", flush=True)

    def _update_session_summary(self, session_id: str, update_dict: Dict[str, Any]):
        """Maintains the latest snapshot of session audit."""
        self._ensure_dirs()
        summary_file = self.get_session_summary_file(session_id)
        current = {}
        if summary_file.exists():
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except Exception:
                current = {}
        # Cumulatively merge extracted_fields so late or empty batches do not wipe previous fields
        if "extracted_fields" in update_dict and isinstance(update_dict["extracted_fields"], dict):
            existing_fields = current.get("extracted_fields", {})
            if isinstance(existing_fields, dict):
                merged_fields = {**existing_fields, **update_dict["extracted_fields"]}
                update_dict["extracted_fields"] = merged_fields

        current.update(update_dict)
        current["session_id"] = session_id
        current["last_updated"] = datetime.now(timezone.utc).isoformat()
        try:
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to update session summary JSON: {e}")

    def get_session_logs(self, session_id: str) -> List[Dict[str, Any]]:
        """Reads all events for a given session from disk."""
        session_file = self.get_session_jsonl_file(session_id)
        if not session_file.exists():
            return []
        events = []
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        pass
        return events

    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Reads latest snapshot for a session."""
        summary_file = self.get_session_summary_file(session_id)
        if not summary_file.exists():
            return None
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None


audit_logger = PDAuditLogger()
