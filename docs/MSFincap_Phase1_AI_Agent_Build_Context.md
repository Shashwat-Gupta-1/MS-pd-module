# MSFincap Phase 1 — AI Agent Build Context
*(Feed this entire file to a coding AI agent as project context. It contains every decision, schema, endpoint, formula, and rule needed to build Phase 1 without further clarification. Where a decision was deferred by the human team, it is marked TBD — do not guess on those.)*

---

## 0. Project Summary

MSFincap is an NBFC (MSME lending + LAP) building an in-house AI-assisted loan-origination system. **Phase 1** covers the Personal Discussion (PD) module only: from application creation to a fully verified, structured, scored case file. It does **not** include credit risk scoring, BRE eligibility decisioning, or CIBIL/bureau integration — those are Phase 2, deliberately out of scope, but Phase 1's data model must be clean enough for Phase 2 to consume without rework.

Build team: 2 developers (Shashwat: backend/agents/infra; Riddhi: frontend/vision-agent-integration/testing). Both know Python and Java; primary stack is Python/FastAPI + Next.js.

**Non-negotiable constraints:**
- No Tele-PD / no telephony provider. PD happens entirely in person, through one web app.
- No native mobile app — one responsive Next.js app serves both desktop and mobile browsers.
- Vision analysis uses an LLM vision API (Gemini/Groq free tier) — **not YOLO** (no custom training data exists yet).
- Land valuation engine is **removed** from Phase 1 entirely.
- Multiple rounds of AI-generated follow-up questions per PD, post-each-answer-batch (not live/streaming mid-speech). Rounds continue until the RAG-retrieved profession checklist is fully covered, or the recording/session ends — whichever comes first. Unanswered/skipped checklist items at session end count against the officer's coverage score.
- RAG knowledge base scope for v1: 20-25 profession/business-category documents.
- Free-tier hosted LLMs (Groq or Gemini) for all text/vision agent calls; self-hosted for speech-to-text (`faster-whisper`) and embeddings (`sentence-transformers`).
- Single FastAPI service, no microservices split. **MVP stage: no Docker, no containerization — run everything directly on one machine/VM** (Postgres, Redis, and the FastAPI/Celery processes installed and run natively). Containerize later once the setup needs to move between environments or scale beyond one box.

---

## 1. Tech Stack (exact)

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router), React, TypeScript, Recharts for admin charts |
| Backend | FastAPI (Python), SQLAlchemy, Alembic |
| Async jobs | Celery + Redis |
| Database | PostgreSQL + `pgvector` extension |
| Speech-to-text | `faster-whisper` (self-hosted) |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`, self-hosted) |
| LLM (text + vision) | Groq or Gemini free tier — isolated behind one client module |
| Maps/geocoding | OpenStreetMap Nominatim or Google Geocoding (small free tier) |
| File storage | Local disk (MVP) → MinIO later |
| PDF rendering | WeasyPrint (HTML/Jinja2 → PDF) |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Deployment | Single VM, run directly (no Docker for MVP) |

---

## 2. Complete Database Schema

```sql
officers (
  id, name, phone, role,              -- role: officer | underwriter | admin
  branch, hashed_password, created_at
)

applicants (
  id, name, phone UNIQUE, pan, aadhaar_number,
  employment_type,                    -- 'self_employed' | 'salaried'
  business_category,                  -- nullable until determined mid-PD
  employer_type,                      -- nullable, salaried only
  created_at
)

applications (
  id, applicant_id FK, product_type, requested_amount, tenure, rate,
  status,                             -- INTAKE | PD_IN_PROGRESS | PD_COMPLETE
  created_at
)

question_bank (
  id, tier,                           -- 1 | 2 | 3
  employment_type, business_category,
  question_text, field_name, data_type, is_mandatory
)

pd_sessions (
  id, application_id FK, officer_id FK,
  channel,                            -- 'ground' (only value used in v1 — no tele-PD)
  recording_url, consent_captured, consent_timestamp,
  transcript_raw,
  status,                             -- recorded | transcribed | needs_manual_review | complete
  gap_round_count,                    -- how many follow-up rounds have run
  checklist_fully_covered BOOLEAN DEFAULT FALSE,  -- set true once RAG checklist has no remaining gaps
  started_at
)

transcript_segments (
  id, pd_session_id FK, start_time, end_time, text, confidence
)

extracted_fields (
  id, pd_session_id FK, field_name, value,
  source,                             -- 'stated' | 'inferred' | 'not_captured'
  confidence_note, officer_confirmed BOOLEAN DEFAULT FALSE
)

gap_questions (
  id, pd_session_id FK, question_text, category, round_number,
  resolved BOOLEAN DEFAULT FALSE, answer, override_reason
)

ground_pd_photos (
  id, application_id FK, category, url,
  lat, lng, accuracy_radius, captured_at
  -- GPS is captured PER PHOTO, not once per visit. This is the primary location-verification mechanism.
)

photo_extractions (
  id, photo_id FK, machinery_type, approx_count,
  employee_count_visible, condition
)

officer_pd_scores (
  id, pd_session_id FK, officer_id FK,
  coverage_score,                     -- % of profession-required checklist items captured
  suggestion_uptake_score,            -- % of AI-suggested gap questions actually asked
  reconfirmation_diligence_score,     -- did officer reconfirm every flagged numeric field
  overall_score, created_at
)

customer_consistency_flags (
  id, pd_session_id FK, field_name,
  value_a, value_a_timestamp, value_b, value_b_timestamp,
  severity,                           -- e.g. 'low' | 'medium' | 'high', based on magnitude of discrepancy
  resolution_note,                    -- filled if officer resolved it on the spot
  created_at
)

bre_preliminary_calcs (
  id, application_id FK,
  emi_calculated, foir_pct, ltv_pct,
  ltv_status,                         -- 'computed' | 'not_applicable' | 'pending_collateral_valuation'
  computed_at
)

officer_remarks (
  id, pd_session_id FK, flag_reference_id,   -- links to a customer_consistency_flag or gap_question if applicable
  structured_response,                        -- officer's answer to "regarding [flag], your assessment?"
  open_remark_text,                           -- genuinely free-text field for anything else observed
  created_at
)
```

**Explicitly removed from this version:** `land_valuation`, `land_rate_history` (land valuation engine dropped per team decision).

---

## 3. Complete API Surface

```
POST   /auth/login                              → JWT
POST   /auth/verify-otp

POST   /applicants                              create applicant (OTP-gated, dedupes by phone/PAN)
POST   /applications                            create application
GET    /applications/{id}                       full case detail
GET    /applications                             list/filter (ops/admin dashboard)
POST   /applications/{id}/submit-pd              triggers completion gate check

GET    /questionnaire/{application_id}           returns applicable Tier 1-3 questions

POST   /pd-sessions                              starts a session, logs consent
POST   /pd-sessions/{id}/end                     uploads recording, enqueues transcribe_audio
GET    /pd-sessions/{id}                         transcript + extracted_fields + gap_questions + consistency_flags
POST   /pd-sessions/{id}/resolve-gap             officer resolves one gap question
POST   /pd-sessions/{id}/reconfirm-field          officer confirms/corrects one flagged numeric field

POST   /ground-pd/photos                         upload photo + GPS/timestamp; enqueues vision extraction

GET    /applications/{id}/report                 returns/generates the assembled PD report (PDF)

GET    /admin/question-bank                      view Tier 1-3 config
POST   /admin/question-bank                      add/edit a question set
GET    /admin/analytics/officer-scores            officer_pd_scores over time, filterable by branch
GET    /admin/analytics/consistency-flags         aggregate customer_consistency_flags trends
GET    /admin/analytics/case-funnel                case status funnel + stage timing metrics
```

---

## 4. Agent Specifications (exact logic each agent must implement)

### Agent 1 — Speech-to-Text
- Input: `pd_sessions.recording_url`
- Process: run `faster-whisper` (small/base model), get transcript + per-segment confidence
- Output: `pd_sessions.transcript_raw`, `transcript_segments` rows
- **Hard rule:** if average confidence < threshold (tune empirically, start at 0.6), set `pd_sessions.status = 'needs_manual_review'` and **stop the pipeline** — do not proceed to Agent 2.

### Agent 2 — Classify + RAG (Gap Analysis)
- Input: `transcript_raw` + Tier 1-2 `extracted_fields` (employment_type known already)
- Step A: LLM call → classify `business_category` (or `employer_type` for salaried)
- Step B: pgvector similarity search using the classified category → retrieve matching profession-guideline document chunk from the RAG store (20-25 docs total for v1)
- Step C: LLM call → extract structured fields from transcript into the schema defined by `question_bank` field_names for this tier/category. **Every field must be tagged with `source`: `stated` (directly quoted/said), `inferred` (model concluded it, not directly stated — must include why), or `not_captured` (never mentioned). Never output a bare value with no source tag.**
- Step D: for any numeric field (income, rate, amount), always set it aside for mandatory officer reconfirmation — this is enforced at the schema level (`extracted_fields.officer_confirmed` defaults `false` and must be flipped `true` via `/reconfirm-field` before Phase 2 can trust it).
- Step E: LLM call → compare the profession document's requirements against what's been extracted; for any gap, **select** (never freely generate) questions from that profession's pre-approved question bank (stored as part of `question_bank` tier=3 rows, or a separate `profession_followup_bank` table if cleaner — agent's choice, but questions must come from a stored, reviewable set, not raw LLM generation). Tag each generated question with the current `round_number`.
- Output: `extracted_fields` rows, `gap_questions` rows (round 1).
- **Fallback rule:** if `business_category` cannot be confidently classified into one of the 20-25 known categories, use a generic fallback question set (must exist in `question_bank` as `business_category = 'general'`) rather than failing.

**Multi-round loop (replaces the earlier single-round design):** After the officer answers Round N's questions, Agent 2 re-runs Step E only (re-comparing the full checklist against the now-larger set of extracted fields, including every prior round's answers). This repeats, incrementing `round_number` and `pd_sessions.gap_round_count` each time, until **one of two stopping conditions is met**:
1. **Checklist fully covered** — every mandatory item in the profession's RAG checklist now has a `stated` or `inferred` value (not `not_captured`). Set `pd_sessions.checklist_fully_covered = true` and stop generating new rounds.
2. **Session ends** — the officer ends the recording/visit (explicit "end session" action) before the checklist is fully covered. Stop immediately; do not force another round.

There is **no fixed round-count cap** — rounds continue purely based on checklist coverage, not a hardcoded number. This means Agent 2 must be re-invoked as a lightweight, cheap re-check after every answer batch (not a heavy re-transcription — only Step C/D/E re-run on the incremental new answers, Step A/B classification and retrieval only need to run once per session).

**Any `gap_questions` row still `resolved = false` when the session ends** (whether skipped by the officer, or left unanswered because the borrower couldn't clarify) is **not deleted or hidden** — it stays on the record, explicitly marked unresolved, and **is a direct negative input to that officer's `coverage_score`** (see Officer Scoring Agent below). This is the enforcement mechanism: an officer who repeatedly skips AI-suggested questions will see it reflected in their score, without the system ever blocking them from ending a session.

### Agent 3 — Vision + GPS Confirmation
- Input: each `ground_pd_photos` row as it's uploaded
- Vision step: send photo to the LLM vision endpoint with a **constrained prompt** — output only fixed fields (`machinery_type`, `approx_count`, `employee_count_visible`, `condition`). Explicitly instruct the model: no free-text description beyond these fields, no evaluative/lifestyle commentary.
- GPS confirmation step (runs once per visit, after all photos for that visit are uploaded): compute pairwise distance between all photos' `lat`/`lng` for this `application_id`; if the cluster spans more than a tolerance threshold (tune empirically, start ~50-100m, widened by each photo's own `accuracy_radius`), raise a location-mismatch flag on the application. Also reverse-geocode the photo cluster's centroid and compare resulting pincode/district against the applicant's stated address — mismatch raises a flag.
- Output: `photo_extractions` rows; a location-confirmation status stored on the `applications` record (add a column `geo_confirmation_status` if not already present: `confirmed` | `flagged` | `insufficient_photos`).

### Officer Scoring Agent
- Runs once a `pd_session` reaches a resolvable end-state (all gaps addressed or explicitly marked unresolvable, all numerics reconfirmed or explicitly left pending).
- `coverage_score` = (mandatory profession-checklist items captured with `source != not_captured`) / (total mandatory items) × 100. **If the session ended with `checklist_fully_covered = false`, every remaining uncovered checklist item counts against this score** — this is what replaces a fixed round cap: there's no limit on how many rounds can run, but ending the session with gaps still open costs the officer directly here.
- `suggestion_uptake_score` = (gap_questions across all rounds where resolved=true) / (total gap_questions generated across all rounds) × 100 — an explicit, logged skip with `override_reason` counts less harshly than a silent ignored question (agent should track skip-with-reason separately from ignored-entirely, if the UI captures that distinction), but both still reduce this score since the point of tracking uptake is to discourage skipping AI suggestions without good reason.
- `reconfirmation_diligence_score`: binary/qualitative — did every numeric field needing reconfirmation get `officer_confirmed = true`? Also check: for any `customer_consistency_flags` on this session, does an `officer_remarks.resolution_note`-equivalent exist? (i.e., did the officer actually address it, not just leave it flagged)
- `overall_score`: a weighted combination of the three above (exact weights are a product decision — default suggestion: 40% coverage, 30% uptake, 30% diligence, but this should be configurable, not hardcoded)
- Output: `officer_pd_scores` row.

### Customer Consistency Agent
- Input: full `transcript_raw` + all `gap_questions.answer` values (gap-question answers happen later in the conversation and must be included in this check)
- Process: LLM call instructed to find any two statements referring to the same fact (income, business age, family size, obligations, any numeric or categorical fact restated) that materially disagree. For each: record both values with their approximate timestamp/segment reference, and assign a `severity` based on magnitude of discrepancy (a small rounding difference is not the same as 2x).
- **This agent's output must never auto-resolve the contradiction or pick which value is "correct."** It only flags; resolution is a human step (officer follow-up + `officer_remarks`).
- Output: `customer_consistency_flags` rows.
- **Explicitly kept separate from Officer Scoring** — a customer being inconsistent is not, by itself, evidence of officer performance either way.

### Report Assembly Agent
- Runs after `applications.status = PD_COMPLETE`.
- Input: everything above, plus `bre_preliminary_calcs` and `officer_remarks`.
- Process: maps every section of MSFincap's PD report template (**template TBD — to be provided by MSFincap; build this agent's mapping logic as configuration-driven, not hardcoded, so the actual template can be dropped in later without a rewrite**) to a data source. Data-only sections render directly (no LLM). Narrative sections (if the template calls for any) are LLM-written under strict constraints: factual only, must be traceable to a specific source field/transcript segment, no unstated inferences, no evaluative/lifestyle language (run a keyword/pattern check against generated text before finalizing).
- The **Customer Response section** (transcript or AI-generated summary, toggle-able) and the **Officer Remarks section** (structured + open) are both first-class sections in the template mapping, not afterthoughts.
- `officer_pd_scores.overall_score` is included in the report but flagged as **internal/underwriter-visible only**, never shown to the borrower.
- PII masking pass runs before generating any wide-circulation version.
- Output: rendered PDF stored in file storage, linked to the application.

---

## 5. Deterministic Calculations (no LLM — pure functions, unit test these)

```python
def calculate_emi(principal: float, annual_rate_pct: float, tenure_months: int) -> float:
    r = (annual_rate_pct / 12) / 100
    return principal * r * (1 + r) ** tenure_months / ((1 + r) ** tenure_months - 1)

def calculate_foir(total_obligations_incl_new_emi: float, net_monthly_income: float) -> float:
    return (total_obligations_incl_new_emi / net_monthly_income) * 100

def calculate_ltv(loan_amount: float, collateral_value: float) -> float:
    return (loan_amount / collateral_value) * 100
    # if no collateral (unsecured product): ltv_status = 'not_applicable', do not compute
    # if collateral case but value unknown (land valuation engine removed): ltv_status = 'pending_collateral_valuation'
```

These run automatically once `net_monthly_income` is `officer_confirmed = true` (for FOIR) — not manually triggered. The EMI calculator shown in the officer's UI is a **separate, client-side-only** implementation of the same formula for live use during the visit — it does not write to the database on its own; only the background-triggered calculation that feeds the report does.

---

## 6. UI Flow (screen sequence — see `docs/ui_flow.md` for full detail per screen)

```
Login → Create Case → Tier 1-3 Questionnaire (recording) → Upload & AI Processing (spinner)
  → Gap Questions + Consistency Flags screen → Numeric Reconfirmation → Photo Capture
  → Review & Submit (+ officer remarks + EMI calculator) → Completion Gate → PD_COMPLETE
```

No Land Boundary Walk step (removed). No Tele-PD step (removed, never existed in this version).

Admin Panel (separate section, role-gated): Officer analytics, consistency-flag trends, case funnel — charted, not raw tables.

---

## 7. Edge Cases the Implementation Must Handle

- Low transcription confidence → hard stop, manual review flag, never silently proceed.
- Misheard numeric fields → mandatory officer reconfirmation before any downstream calculation trusts them.
- Unclassifiable business category → generic fallback question set, never a pipeline failure.
- Officer ignoring AI-suggested gap questions → logged (uptake score), not blocked, but visible.
- GPS cluster mismatch across a visit's photos → flagged, not auto-rejected.
- Customer statement contradictions → flagged with both values + timestamps, never auto-resolved to one value.
- Incomplete PD (missing mandatory field/photo/unresolved gap) → completion gate blocks `PD_COMPLETE` with a specific missing-items list, never a silent pass.
- PII in reports → masked automatically before wide circulation, not a manual step.
- LLM/vision provider outage → isolated behind `llm_client.py`; retry/backoff logic belongs there, not scattered across agents.

---

## 8. Explicitly Out of Scope for Phase 1 (do not build)

- Any credit risk scoring, BRE eligibility decisioning, CIBIL/bureau pull, CAM generation — Phase 2.
- Land valuation engine (removed).
- Tele-PD / telephony integration (never part of this version).
- YOLO / custom-trained vision model (deferred — vision-LLM only for v1).
- Live/streaming in-call AI question nudging (one post-transcript round only).
- Native mobile app (responsive web only).

## 9. Open Items Marked TBD

- Exact MSFincap PD report template (Report Assembly Agent must be built config-driven to accept this later without rework).
- Exact weighting formula for `officer_pd_scores.overall_score` (default 40/30/30 suggested, confirm with product/credit team).
- Transcription confidence threshold (start at 0.6, tune empirically against real audio).
- GPS cluster tolerance threshold (start at 50-100m, tune empirically).

Build everything else as specified above without further clarification.
