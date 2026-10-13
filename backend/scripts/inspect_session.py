import sys
import json
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

log_file = Path("logs/sessions/45fcfac5-2401-4da1-a60b-c5ff16c43db9.jsonl")
if not log_file.exists():
    print("File not found")
    sys.exit(1)

with open(log_file, "r", encoding="utf-8") as f:
    records = [json.loads(line) for line in f if line.strip()]

pipeline_runs = [r for r in records if r.get("event_type") == "LANGGRAPH_PIPELINE_EXECUTED"]
print(f"Total Pipeline Batch Executions: {len(pipeline_runs)}\n")

cumulative_fields = {}
for r in pipeline_runs:
    seq = r.get("chunk_sequence")
    transcripts = r.get("whisper_transcript_summary", [])
    extracted = r.get("langgraph_nodes", {}).get("node_3_extraction", {}).get("fields", {})
    cumulative_fields.update(extracted)
    questions = r.get("langgraph_nodes", {}).get("node_6_dynamic_questions", {}).get("questions", [])
    contradictions = r.get("langgraph_nodes", {}).get("node_5_contradictions", {}).get("flags", [])

    print(f"==================== BATCH #{seq} ====================")
    print(f"🎤 Transcripts ({len(transcripts)} turns):")
    for t in transcripts:
        print(f"   • \"{t}\"")
    
    print(f"📊 Fields Captured in this Batch ({len(extracted)}):")
    for k, v in extracted.items():
        print(f"   + {k}: {v.get('value')} (source: {v.get('source')})")

    if questions:
        print(f"❓ Generated Follow-up Questions ({len(questions)}):")
        for q in questions[:3]:
            print(f"   ? {q}")

    if contradictions:
        print(f"⚠️ Contradictions Detected ({len(contradictions)}):")
        for c in contradictions:
            print(f"   ! {c.get('field_name')}: '{c.get('stated_value_1')}' vs '{c.get('stated_value_2')}' ({c.get('severity')})")
    print()

print(f"{'='*60}")
print(f"🏆 CUMULATIVE UNIQUE FIELDS EXTRACTED ACROSS INTERVIEW: {len(cumulative_fields)}")
for k, v in cumulative_fields.items():
    print(f"  • {k:42} : {v.get('value')} [{v.get('source')}]")
print(f"{'='*60}\n")
