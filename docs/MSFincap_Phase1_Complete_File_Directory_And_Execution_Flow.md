# MSFincap Phase 1 — Complete File Directory, Architecture & Execution Flow Guide

This document provides an exhaustive, file-by-file breakdown of every directory, file, and subfile in the **MSFincap Phase 1** codebase. It explains what each file does, how files connect to one another, details the full end-to-end execution flow of the platform, and clarifies why certain 1-line/stub files exist in the repository.

---

## Table of Contents
1. [Exhaustive Codebase Inventory & File Breakdown](#1-exhaustive-codebase-inventory--file-breakdown)
   - [1.1 Root & Configuration Files](#11-root--configuration-files)
   - [1.2 `backend/app/core/` (Configuration, Database & Security)](#12-backendappcore-configuration-database--security)
   - [1.3 `backend/app/models/` (SQLAlchemy Relational ORM Layer)](#13-backendappmodels-sqlalchemy-relational-orm-layer)
   - [1.4 `backend/app/schemas/` (Pydantic Data Validation & DTOs)](#14-backendappschemas-pydantic-data-validation--dtos)
   - [1.5 `backend/app/calculations/` (Pure Deterministic Math Engine)](#15-backendappcalculations-pure-deterministic-math-engine)
   - [1.6 `backend/app/rag/` (ChromaDB Vector Store & Knowledge Base)](#16-backendapprag-chromadb-vector-store--knowledge-base)
   - [1.7 `backend/app/agents/` (LangGraph Pipeline & AI Underwriting)](#17-backendappagents-langgraph-pipeline--ai-underwriting)
   - [1.8 `backend/app/api/` (FastAPI REST Routes & Dependency Injection)](#18-backendappapi-fastapi-rest-routes--dependency-injection)
   - [1.9 `backend/app/utils/` (Validation & Security Utilities)](#19-backendapputils-validation--security-utilities)
   - [1.10 `backend/app/workers/` (Celery Tasks & Async Processing)](#110-backendappworkers-celery-tasks--async-processing)
   - [1.11 `backend/app/data/questions/` (File-Driven Questionnaire JSONs)](#111-backendappdataquestions-file-driven-questionnaire-jsons)
   - [1.12 `backend/app/tests/` (Pytest Test Suite)](#112-backendapptests-pytest-test-suite)
   - [1.13 `backend/logs/` (Tamper-Evident On-Device Audit Logs)](#113-backendlogs-tamper-evident-on-device-audit-logs)
   - [1.14 `docs/` (System Documentation & Specifications)](#114-docs-system-documentation--specifications)
2. [Why Are There "Empty" / 1-Line Stub Files?](#2-why-are-there-empty--1-line-stub-files)
3. [Complete End-to-End System Execution Flow](#3-complete-end-to-end-system-execution-flow)
   - [Step 1: Application Boot & Data Ingestion](#step-1-application-boot--data-ingestion)
   - [Step 2: Officer Authentication & Case Assignment](#step-2-officer-authentication--case-assignment)
   - [Step 3: Ground PD Session Initialization](#step-3-ground-pd-session-initialization)
   - [Step 4: Live Audio Ingestion & LangGraph Processing](#step-4-live-audio-ingestion--langgraph-processing)
   - [Step 5: ChromaDB RAG Benchmark Matching](#step-5-chromadb-rag-benchmark-matching)
   - [Step 6: Officer Numeric Reconfirmations & Remarks](#step-6-officer-numeric-reconfirmations--remarks)
   - [Step 7: Completion Gate Enforcement](#step-7-completion-gate-enforcement)
   - [Step 8: Credit Assessment Memorandum (CAM) Generation](#step-8-credit-assessment-memorandum-cam-generation)
   - [Step 9: Admin Quality Analytics & Proactive Leaderboard](#step-9-admin-quality-analytics--proactive-leaderboard)

---

## 1. Exhaustive Codebase Inventory & File Breakdown

### 1.1 Root & Configuration Files
- **`backend/requirements.txt`**: Defines Python dependencies: FastAPI, Uvicorn, SQLAlchemy, Alembic, Pydantic, Passlib, PyJWT, ChromaDB, LangGraph, Groq, WeasyPrint, Jinja2, Celery, Redis, Pytest.
- **`backend/.env.example`**: Template environment variables (`DATABASE_URL`, `SECRET_KEY`, `GROQ_API_KEY`, `CHROMA_PERSIST_DIRECTORY`, `REDIS_URL`, `TESTING`).
- **`backend/alembic.ini`**: Alembic database migration configuration mapping migration scripts to target database URLs.
- **`backend/alembic/env.py`**: Migration runtime environment that imports SQLAlchemy declarative `Base` to auto-detect schema changes.

---

### 1.2 `backend/app/core/` (Configuration, Database & Security)
- **`app/core/config.py`**:
  - Implements the Pydantic `Settings` singleton class.
  - Loads environment variables with defaults: JWT expiration (60 mins), database path (`msfincap.db` or PostgreSQL), ChromaDB persist directory (`chroma_db/`), Groq model identifiers (`llama-3.3-70b-versatile`), and file upload paths.
- **`app/core/database.py`**:
  - Creates the SQLAlchemy DB engine with connection pooling.
  - Exposes `SessionLocal` for thread-safe database sessions and declarative `Base`.
  - Exposes the `get_db()` generator dependency injected into FastAPI routes.
- **`app/core/security.py`**:
  - Implements password hashing via `passlib[bcrypt]` (`verify_password`, `get_password_hash`).
  - Implements JWT encoding and decoding (`create_access_token`, `decode_access_token`).
  - Manages a lightweight 6-digit OTP generator and memory-backed store (`send_otp_mock`, `verify_otp_code`).

---

### 1.3 `backend/app/models/` (SQLAlchemy Relational ORM Layer)
The relational schema comprises **15 models** that store audit-ready underwriting records:

| File | Primary Model | Purpose & Data Managed |
|---|---|---|
| **`__init__.py`** | *Package Export* | Exports all 15 models so Alembic and `database.py` discover tables in a single import. |
| **`applicant.py`** | `Applicant` | Borrower personal data: full name, PAN, phone number, hashed Aadhaar, KYC status, and deduplication records. |
| **`application.py`** | `Application` | Loan application file: requested loan amount, tenure, purpose, interest rate, case status (`DRAFT`, `PD_SCHEDULED`, `IN_PROGRESS`, `PD_COMPLETE`, `APPROVED`, `REJECTED`). |
| **`bre_preliminary_calc.py`** | `BREPreliminaryCalc` | Audit log of deterministic financial math calculations: monthly income, debt obligations, proposed EMI, FOIR %, LTV %, and loan status (`ELIGIBLE`, `POLICY_BREACH`). |
| **`customer_consistency_flag.py`** | `CustomerConsistencyFlag` | Tracks contradictions across borrower statements (e.g. stated income ₹80,000 in batch 1 vs. ₹40,000 in batch 3), severity level (`LOW`, `MEDIUM`, `HIGH`), and quote excerpts. |
| **`extracted_field.py`** | `ExtractedField` | Financial and operational parameters extracted from transcripts (turnover, profit margin, rent, inventory cycle) with confidence score and state (`STATED`, `INFERRED`, `NOT_CAPTURED`). |
| **`gap_question.py`** | `GapQuestion` | Dynamically formulated follow-up questions generated by AI to cover missing RAG checklist items; status (`PENDING`, `ASKED`, `SATISFIED`). |
| **`ground_pd_photo.py`** | `GroundPDPhoto` | Metadata for on-site photos (stock, machinery, shopfront, premise), perceptual image hash (`dhash_hex`), GPS coordinates, and timestamp. |
| **`officer.py`** | `Officer` | Field credit officer profiles: name, branch code, phone number, email, role (`CREDIT_OFFICER`, `BRANCH_MANAGER`, `ADMIN`), hashed password. |
| **`officer_pd_score.py`** | `OfficerPDScore` | Objective diligence evaluation: total suggested gap questions, count asked by officer, calculated uptake %, and unprompted proactive diligence bonus score. |
| **`officer_remark.py`** | `OfficerRemark` | Qualitative human underwriter notes: neighborhood market reputation, footfall observed, business premise condition, borrower demeanor. |
| **`pd_session.py`** | `PDSession` | Ground verification session lifecycle: start/stop timestamps, recording duration, audio file path, session status (`ACTIVE`, `COMPLETED`, `CANCELLED`). |
| **`photo_extraction.py`** | `PhotoExtraction` | Structured parameters derived from photo inspection: machinery type, equipment condition, estimated stock value, visible employee count. |
| **`profession_profile.py`** | `ProfessionProfile` | Relational table storing benchmark parameters for informal businesses (min/max gross margin %, working capital turnover days, required RAG checklist items, operational red flags). |
| **`question_bank.py`** | `QuestionBank` | Standardized questionnaire bank loaded from external JSON files (Tier 1 universal, Tier 2 trade-specific, Tier 3 risk triggers). |
| **`transcript_segment.py`** | `TranscriptSegment` | Audio transcript segments: batch sequence number, start/end timestamps, speaker tag (`OFFICER`, `BORROWER`), raw text, confidence score. |

---

### 1.4 `backend/app/schemas/` (Pydantic Data Validation & DTOs)
34 validation schemas ensure strict data contract compliance across all API requests and responses:
- **`app/schemas/applicant.py`**: Validates PAN regex format, phone numbers, KYC submission, and applicant responses.
- **`app/schemas/application.py`**: Validates loan applications, updates, and status transitions.
- **`app/schemas/auth.py`**: Login payloads (`username`, `password`), JWT bearer token responses, and OTP verification requests.
- **`app/schemas/bre_preliminary_calc.py`**: Calculation payloads and audited calculation result models.
- **`app/schemas/customer_consistency_flag.py`**: Contradiction flag creation, status updates, and case severity summary schemas.
- **`app/schemas/extracted_field.py`**: Transcribed entity extraction, 3-state tracking (`STATED`/`INFERRED`/`NOT_CAPTURED`), and officer reconfirmations.
- **`app/schemas/gap_question.py`**: Follow-up question payloads, priority scoring, and resolution triggers.
- **`app/schemas/ground_pd_photo.py`**: Photo upload validation, dHash responses, and GPS cluster verification schemas.
- **`app/schemas/officer.py`**: Officer creation, profile updates, and admin role assignments.
- **`app/schemas/officer_pd_score.py`**: Diligence scoring payloads, question counts, and proactive diligence bonus breakdown.
- **`app/schemas/officer_remark.py`**: Human underwriter field notes validation.
- **`app/schemas/pd_session.py`**: Session creation, batch ingestion, end-session signals, and live state view schemas.
- **`app/schemas/photo_extraction.py`**: Structured vision output validation schemas.
- **`app/schemas/question_bank.py`**: Tiered questionnaire JSON ingestion and retrieval schemas.

---

### 1.5 `backend/app/calculations/` (Pure Deterministic Math Engine)
- **`app/calculations/emi_foir_ltv.py`**:
  - Contains **pure deterministic arithmetic functions** for credit math:
    - `calculate_emi(principal, annual_interest_rate, tenure_months)`: Implements standard reducing-balance amortization formula.
    - `calculate_foir(monthly_income, existing_obligations, proposed_emi)`: Calculates Fixed Obligation to Income Ratio with decimal precision.
    - `calculate_ltv(loan_amount, property_valuation, is_secured)`: Calculates Loan-to-Value percentage for secured facilities; returns `0.0` or marks `PENDING_VALUATION` when unvalued.
  - **Critical Architectural Rule**: **Zero LLM involvement** in calculations. Fully tested across 16 unit tests covering boundary conditions, zero values, and negative checks.

---

### 1.6 `backend/app/rag/` (ChromaDB Vector Store & Knowledge Base)
- **`app/rag/chroma_client.py`**:
  - Singleton ChromaDB client manager.
  - In normal/production mode, connects to a persistent on-disk ChromaDB directory (`chroma_db/`).
  - In test mode (`CHROMA_EPHEMERAL="true"`), switches to `chromadb.EphemeralClient()` to guarantee in-memory test isolation.
  - Creates and manages the `profession_profiles` collection with **cosine distance space** (`hnsw:space: cosine`).
- **`app/rag/ingest_profession_profiles.py`**:
  - Ingestion engine that parses `docs/MSFincap_RAG_Business_Profiles.md`.
  - Extracts 8 comprehensive informal business profiles (Kirana Store, Small Manufacturing, Dairy & Livestock, Wholesale Trading, Transportation, Textile & Apparel, Restaurant & Eatery, Personal Services).
  - Embeds markdown content directly into the ChromaDB `profession_profiles` collection with metadata.
  - Concurrently syncs relational structured benchmarks (margins, turnover, required checklists) into the `ProfessionProfile` SQL table.
  - Provides a CLI runner (`python -m app.rag.ingest_profession_profiles`).
- **`app/rag/retrieval.py`**:
  - Two-stage hybrid retriever:
    1. **Stage 1 (Exact Match)**: Case-insensitive SQL lookup on `ProfessionProfile.sub_profile_name` or `category`.
    2. **Stage 2 (ChromaDB Semantic Fallback)**: If exact match fails, queries ChromaDB's vector collection (`collection.query(query_texts=[sub_profile], n_results=1)`), retrieves the nearest neighbor ID, and fetches the benchmark profile.
    3. **Cold Start Auto-Seeding**: Automatically seeds ChromaDB and the SQL database if 0 profiles exist.
- **`app/rag/ingest_profession_docs.py`**:
  - *Legacy stub file* from initial scaffolding before ChromaDB was adopted (see Section 2).

---

### 1.7 `backend/app/agents/` (LangGraph Pipeline & AI Underwriting)
- **`app/agents/llm_client.py`**:
  - Unified adapter for the Groq API (`llama-3.3-70b-versatile` for reasoning, `llama-3.2-11b-vision-preview` for photo inspection).
  - Handles JSON auto-correction (extracting clean JSON from markdown code fences).
  - Implements exponential backoff on HTTP 429 (rate limits) and 5xx errors.
  - Provides simulation fallback mode for unit test isolation.
- **`app/agents/pd_workflow_graph.py`**:
  - The central **7-node stateful LangGraph pipeline** managing the real-time ground interview:
    1. `ingest_batch`: Deduplicates streaming transcript chunks by timestamp and sequence.
    2. `evaluate_diligence`: Scans transcripts to determine if the officer asked suggested gap questions (uptake) and awards unprompted diligence bonuses if the officer asked proactive, smart underwriting questions.
    3. `extract_fields`: Extracts financial and operational values, mapping them to 3 states (`STATED`, `INFERRED`, `NOT_CAPTURED`) and flagging numeric fields for officer reconfirmation.
    4. `check_consistency`: Performs pairwise cross-statement contradiction analysis across all accumulated transcript batches.
    5. `analyze_gaps`: Compares captured fields against the business's RAG checklist; enforces a **15-word cost guard** to skip calling LLM on tiny audio silences.
    6. `generate_followups`: Dynamically formulates context-aware follow-up questions in natural Hindi/Hinglish (no pre-scripted banks).
    7. `mark_resolved`: Reconciles state when a session completes.
  - Persists state with `MemorySaver` checkpointer and writes tamper-evident audit logs to `logs/pd_session_{id}.jsonl`.
- **`app/agents/report_narrative.py`**:
  - Underwriting narrative generator for Section 11 of the CAM report.
  - Scans generated text against a list of forbidden subjective/lifestyle adjectives (`opulent`, `humble`, `rich`, `poor`, `luxurious`).
  - Auto-retries once on detection; flags for manual review if second attempt still contains subjective phrasing.
- **`app/agents/report_assembly.py`**:
  - End-to-end report compiler that pulls all verified case facts, photos, deterministic calculations, and AI narratives into a Jinja2 HTML template and compiles it into an official PDF via WeasyPrint.
- **`app/agents/officer_scoring.py`**:
  - Calculates officer diligence metrics: `uptake_percentage = (asked_count / total_recommended) * 100` (defaults to 100% when zero gaps were needed), and aggregates proactive diligence bonus points.
- **`app/agents/customer_consistency.py`**:
  - Rollup helper that counts active contradiction flags by severity (`LOW`, `MEDIUM`, `HIGH`) to determine overall borrower integrity risk.
- **`app/agents/speech_to_text.py`**, **`app/agents/vision_extraction.py`**, **`app/agents/classify_rag.py`**, **`app/agents/embeddings.py`**:
  - *Pre-existing integration stubs* from the project scaffolding (see Section 2).

---

### 1.8 `backend/app/api/` (FastAPI REST Routes & Dependency Injection)
- **`app/api/deps.py`**:
  - Dependency injection functions: `get_db`, `get_current_user`, `get_current_officer`, `get_current_admin`. Validates JWT tokens and checks user roles.
- **`app/api/routes/auth.py`**:
  - Authentication endpoints: `/auth/login`, `/auth/otp/send`, `/auth/otp/verify`, `/auth/me`, `/health`.
- **`app/api/routes/applicants.py`**:
  - Applicant intake endpoints: `POST /applicants` (with PAN deduplication), `GET /applicants`, `GET /applicants/{id}`.
- **`app/api/routes/applications.py`**:
  - Case file endpoints: `POST /applications` (initializes case, executes preliminary deterministic BRE calculations), `GET /applications/{id}`, status transition triggers.
- **`app/api/routes/questionnaire.py`**:
  - File-driven questionnaire endpoints: `GET /questionnaire/tiers`, `GET /questionnaire/tiers/{tier_id}`, `POST /questionnaire/reload` (scans JSON files without database migrations).
- **`app/api/routes/pd_sessions.py`**:
  - Complete Ground PD execution router:
    - `POST /pd-sessions`: Starts session.
    - `POST /pd-sessions/{id}/batch`: Ingests streaming audio transcript batches and executes the LangGraph workflow.
    - `GET /pd-sessions/{id}/live-state`: Feeds live updates (suggested prompts, diligence bonus, captured fields) to the officer's mobile interface.
    - `POST /pd-sessions/{id}/reconfirm`: Allows officer to reconfirm or adjust key extracted numbers (turnover, margin, household income).
    - `POST /pd-sessions/{id}/manual-field`: Manual field entry fallback for noisy audio.
    - `POST /pd-sessions/{id}/remarks`: Submits qualitative field notes.
    - `POST /pd-sessions/{id}/end-session`: Executes completion gate checks and concludes the interview.
- **`app/api/routes/admin.py`**:
  - Administrative oversight router:
    - `GET /admin/scores`: Officer diligence scoring analytics.
    - `GET /admin/consistency-flags`: Customer contradiction risk analytics.
    - `GET /admin/cases`: Case funnel distribution.
    - `GET /admin/leaderboard`: Officer proactive diligence bonus rankings.
- **`app/api/routes/ground_pd.py`**, **`app/api/routes/reports.py`**:
  - *Legacy stub files* from initial scaffolding (see Section 2).

---

### 1.9 `backend/app/utils/` (Validation & Security Utilities)
- **`app/utils/completion_gate.py`**:
  - Verification gatekeeper ensuring an application cannot transition to `PD_COMPLETE` unless:
    1. An active or completed PD session exists with recording.
    2. At least one transcript segment exists.
    3. Mandatory financial fields are confirmed.
    4. Required premise photos are uploaded.
    5. Officer qualitative remarks are submitted.
- **`app/utils/image_hash.py`**:
  - Perceptual difference hashing (`dHash`) implementation.
  - Computes 16-character hexadecimal hash of images.
  - Computes Hamming distance between hashes to detect duplicate or recycled photos (fraud prevention).
- **`app/utils/pii_masking.py`**:
  - Redaction utilities that mask PANs (`ABCDE****F`), Aadhaar (`********1234`), phone numbers (`******1234`), and bank accounts before data is sent to external LLMs or logged.
- **`app/utils/gps_utils.py`**:
  - Haversine distance calculator and GPS cluster consistency validator.

---

### 1.10 `backend/app/workers/` (Celery Tasks & Async Processing)
- **`app/workers/celery_app.py`**:
  - Celery distributed task queue configuration backed by Redis.
- **`app/workers/tasks.py`**:
  - Asynchronous background tasks:
    - `process_audio_batch_task`: Asynchronously runs LangGraph processing on incoming audio batches.
    - `generate_pd_report_task`: Compiles CAM PDF reports in the background.
    - `transcribe_audio_stub`: Explicit placeholder for Riddhi's speech-to-text pipeline (raises `NotImplementedError`).
    - `extract_photo_stub`: Explicit placeholder for Riddhi's YOLO/vision pipeline (raises `NotImplementedError`).

---

### 1.11 `backend/app/data/questions/` (File-Driven Questionnaire JSONs)
- **`tier1_standard.json`**: Universal baseline questions asked to every micro-enterprise applicant (business vintage, ownership, premises rent, monthly sales, household expenses, existing loans).
- **`tier2_business_specific.json`**: Industry-specific operational questions categorized by trade ( Kirana supplier terms, manufacturing electricity bills, transport vehicle maintenance).
- **`tier3_exception_triggers.json`**: Red-flag drill-down questions triggered when contradictions, high debt, or unusual cash volumes appear.

---

### 1.12 `backend/app/tests/` (Pytest Test Suite)
The test suite consists of **64 comprehensive tests** executing with 100% pass rate:
- **`conftest.py`**: Pytest environment configuration; sets `CHROMA_EPHEMERAL="true"` to isolate vector tests in RAM and provides SQLite database fixtures and test client dependencies.
- **`test_calculations.py`** (16 tests): Pure unit tests for EMI, FOIR, and LTV edge cases, zero-principal, zero-interest, and negative value validations.
- **`test_auth.py`** (8 tests): Password hashing, JWT creation/validation, OTP generation/verification, and protected route access.
- **`test_applications.py`** (4 tests): Applicant creation, PAN deduplication, application status lifecycle, and file-driven questionnaire hot-reloading.
- **`test_utilities.py`** (13 tests): dHash image hashing, Hamming distance, PII regex masking, and completion gate enforcement.
- **`test_llm_client.py`** (4 tests): Groq client completions, JSON extraction recovery, vision formatting, and rate-limit retry logic.
- **`test_rag.py`** (3 tests): ChromaDB document ingestion, exact-match retrieval, and semantic vector similarity fallback.
- **`test_workflow_graph.py`** (6 tests): LangGraph 7-node pipeline steps (deduplication, diligence evaluation, field extraction, consistency checking, 15-word cost guard, and full graph execution).
- **`test_scoring_and_consistency.py`** (3 tests): Officer uptake scoring, proactive bonus decoupling, and customer contradiction severity rollups.
- **`test_session_routes.py`** (1 test): Complete ground PD session lifecycle endpoints.
- **`test_report_assembly.py`** (2 tests): Underwriter narrative generation (with forbidden tone detection) and PDF compilation.
- **`test_admin_routes.py`** (4 tests): Admin analytics endpoints for scores, consistency flags, case funnel, and officer leaderboard.
- **`test_completion_gate.py`**, **`test_customer_consistency.py`**, **`test_gap_rounds.py`**:
  - *Pre-existing 1-line skeleton stubs* from initial setup (see Section 2).

---

### 1.13 `backend/logs/` (Tamper-Evident On-Device Audit Logs)
- **`pd_session_{id}.jsonl`**:
  - JSON-Lines structured log files generated locally on the device during each PD session.
  - Every batch ingestion, extracted field, contradiction flag, AI follow-up recommendation, and officer reconfirmation is appended immediately.
  - Ensures a tamper-evident audit record survives local device crashes or connectivity loss.

---

### 1.14 `docs/` (System Documentation & Specifications)
- **`MSFincap_Phase1_Decisions_And_Implementation_Log.md`**: Complete log of architectural decisions D-01 through D-11.
- **`MSFincap_Phase1_System_Architecture_And_Code_Reference.md`**: Comprehensive architectural guide, diagrams, and component interactions.
- **`MSFincap_RAG_Business_Profiles.md`**: Credit underwriting domain knowledge base containing 8 informal enterprise profiles, financial benchmark ratios, and verification checklists.
- **`MSFincap_Phase1_Team_Reference.md`**: Developer scope split and interface contracts between My scope (Core backend, RAG, LangGraph, calculations) and Riddhi's scope (STT, YOLO, image storage).

---

## 2. Why Are There "Empty" / 1-Line Stub Files?

In the repository, you will observe several files that contain only a single-line docstring:
1. `app/agents/speech_to_text.py`
2. `app/agents/vision_extraction.py`
3. `app/agents/classify_rag.py`
4. `app/agents/embeddings.py`
5. `app/api/routes/ground_pd.py`
6. `app/api/routes/reports.py`
7. `app/rag/ingest_profession_docs.py`
8. `app/tests/test_completion_gate.py`
9. `app/tests/test_customer_consistency.py`
10. `app/tests/test_gap_rounds.py`

### Why They Exist and What Their Purpose Is:

#### Category A: External Integration Contracts (Belonging to Riddhi)
- **`app/agents/speech_to_text.py`** and **`app/agents/vision_extraction.py`**:
  - **Origin**: Created during initial project setup to mark where local speech-to-text (Whisper) and YOLO computer vision models would sit.
  - **Current Role**: Per the project scope contract, all audio transcription and photo object detection belong to **Riddhi's scope**. In our backend, these are formalized as explicit stubs in `app/workers/tasks.py` (`transcribe_audio_stub` and `extract_photo_stub`) which cleanly raise `NotImplementedError`. These files remain as placeholder boundaries for when Riddhi merges her model services.

#### Category B: Legacy Scaffolding Superseded by Unified Implementations
- **`app/agents/classify_rag.py`** and **`app/agents/embeddings.py`**:
  - **Origin**: Initial design drafted multiple standalone agent scripts and raw `sentence-transformers` embedding wrappers.
  - **What Superseded Them**: In Phase 1 implementation, classification, gap analysis, and dynamic question formulation were unified into the **7-node LangGraph pipeline (`app/agents/pd_workflow_graph.py`)**, and embeddings are now natively handled by **ChromaDB (`app/rag/chroma_client.py`)**.
- **`app/rag/ingest_profession_docs.py`**:
  - **Origin**: Early placeholder for a script intended to chunk documents into PostgreSQL `pgvector`.
  - **What Superseded It**: Superseded by **`app/rag/ingest_profession_profiles.py`**, which embeds `MSFincap_RAG_Business_Profiles.md` into ChromaDB and syncs SQL benchmarks.
- **`app/api/routes/ground_pd.py`** and **`app/api/routes/reports.py`**:
  - **Origin**: Early mock route declarations.
  - **What Superseded Them**: All ground discussion interactions (photo uploads, batch processing, remarks, reconfirmations) are now centralized in **`app/api/routes/pd_sessions.py`**, while report assembly is handled by **`app/agents/report_assembly.py`**.

#### Category C: Scaffolding Test Stubs
- **`app/tests/test_completion_gate.py`**, **`test_customer_consistency.py`**, **`test_gap_rounds.py`**:
  - **Origin**: Placeholder test files created during initial repository initialization.
  - **Where the Tests Actually Live**:
    - Completion gate tests were implemented in `app/tests/test_utilities.py::TestCompletionGate`.
    - Customer consistency tests were implemented in `app/tests/test_scoring_and_consistency.py`.
    - Multi-round gap tests were implemented in `app/tests/test_workflow_graph.py`.
  - All 64 tests run and pass without requiring these 1-line files.

---

## 3. Complete End-to-End System Execution Flow

The following diagram and step-by-step walkthrough illustrate exactly how data moves through the MSFincap Phase 1 system:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 1. SYSTEM STARTUP                                      │
│  FastAPI boots -> Creates DB tables -> Loads Tier JSONs -> Seeds ChromaDB Profiles     │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                             2. INTAKE & PRE-CALCULATION                                │
│  Applicant created (PAN deduplicated) -> Application submitted -> BRE calculates       │
│  Deterministic FOIR, EMI & LTV -> Stored in bre_preliminary_calcs                      │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                           3. GROUND PD SESSION INITIATION                              │
│  Officer logs in (JWT/OTP) -> POST /pd-sessions -> Status: IN_PROGRESS                 │
│  Continuous audio recording starts on field device                                    │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                     4. STREAMING AUDIO BATCH PROCESSING (LANGGRAPH)                     │
│  Device sends 15-20s audio transcript chunks -> POST /pd-sessions/{id}/batch           │
│                                                                                        │
│  ┌───────────────────────── LangGraph 7-Node Execution ──────────────────────────────┐ │
│  │ Node 1 (ingest_batch): Deduplicate transcript by timestamp                          │ │
│  │ Node 2 (evaluate_diligence): Score uptake on suggested questions & diligence bonus  │ │
│  │ Node 3 (extract_fields): Extract turnover, margins, rent (3 states: STATED/INFERRED)│ │
│  │ Node 4 (check_consistency): Cross-batch pairwise contradiction check (LOW/MED/HIGH) │ │
│  │ Node 5 (analyze_gaps): Cost guard (skip <15 words) -> Match RAG required checklist  │ │
│  │ Node 6 (generate_followups): ChromaDB lookup -> Formulate dynamic Hindi questions   │ │
│  │ Node 7 (mark_resolved): Reconcile state & checkpointer                              │ │
│  └───────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                        │
│  Live state streamed to Officer UI:                                                    │
│  • Green Card: Stated fields captured                                                  │
│  • Yellow Card: Dynamic follow-up question to ask next                                 │
│  • Blue Badge: Unprompted proactive diligence bonus awarded                            │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                      5. OFFICER NUMERIC CONFIRMATION & REMARKS                         │
│  Officer reconfirms key financial figures (POST /{id}/reconfirm)                       │
│  Officer submits qualitative observations & footfall (POST /{id}/remarks)              │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                               6. COMPLETION GATE                                       │
│  Officer calls POST /pd-sessions/{id}/end-session                                      │
│  Completion Gate checks: [Recording ✓] [Transcripts ✓] [Reconfirmed ✓] [Photos ✓]      │
│  -> If valid: Application status -> PD_COMPLETE                                        │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                       7. CAM REPORT ASSEMBLY & PDF COMPILATION                         │
│  Jinja2 pulls ground data + pure math calculations + LLM narrative (Section 11)        │
│  Anti-lifestyle adjective filter validates tone -> WeasyPrint compiles final PDF CAM  │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
┌──────────────────────────────────────────▼─────────────────────────────────────────────┐
│                           8. ADMIN QUALITY AUDIT API                                   │
│  Management reviews /admin/scores, /admin/consistency-flags, /admin/leaderboard        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Step 1: Application Boot & Data Ingestion
1. **Server Initialization**: FastAPI initializes via `app/main.py`.
2. **Database Schema Verification**: SQLAlchemy checks or creates tables for all 15 ORM models in `app/models/`.
3. **Questionnaire Auto-Scan**: `app/api/routes/questionnaire.py` loads `data/questions/*.json` into the `question_bank` table.
4. **ChromaDB Connection**: `app/rag/chroma_client.py` initializes the `profession_profiles` collection. If empty, `app/rag/ingest_profession_profiles.py` embeds the 8 domain profiles from `docs/MSFincap_RAG_Business_Profiles.md`.

### Step 2: Officer Authentication & Case Assignment
1. Field officers authenticate at `POST /auth/login` using phone/password or `POST /auth/otp/verify`.
2. A cryptographically signed JWT token containing officer ID and role is issued.
3. The officer retrieves assigned loan cases via `GET /applications`.

### Step 3: Ground PD Session Initialization
1. When the credit officer arrives at the borrower's shop/premise, they press **"Start PD"**.
2. Frontend calls `POST /pd-sessions` with the `application_id`.
3. A `PDSession` record is created with status `IN_PROGRESS`, and an audit log file `logs/pd_session_{id}.jsonl` is opened on disk.
4. Continuous audio recording begins on the mobile device.

### Step 4: Live Audio Ingestion & LangGraph Processing
1. As the discussion progresses, the mobile app sends timestamped transcript chunks (every 15–20 seconds) to `POST /pd-sessions/{id}/batch`.
2. The batch triggers the **7-node LangGraph pipeline (`app/agents/pd_workflow_graph.py`)**:
   - **Node 1 (`ingest_batch`)**: Validates that segments are not duplicated.
   - **Node 2 (`evaluate_diligence`)**: Evaluates whether the officer asked previous AI-suggested questions (increasing uptake %) and awards an unprompted diligence bonus if the officer independently asked smart, unscripted credit questions.
   - **Node 3 (`extract_fields`)**: Identifies declared financial numbers (daily sales, margins, rent) and flags them for numeric confirmation.
   - **Node 4 (`check_consistency`)**: Compares newly extracted figures against all prior statements to detect contradictions (e.g., borrower claiming ₹2,00,000 monthly sales but ₹1,000 daily footfall). Flags are written to `customer_consistency_flags`.
   - **Node 5 (`analyze_gaps`)**: Filters out short audio (< 15 words). Compares extracted fields against the RAG checklist for that specific trade.
   - **Node 6 (`generate_followups`)**: Uses ChromaDB to identify missing benchmark criteria and calls Groq LLM to formulate natural, context-aware Hindi/Hinglish follow-up questions.
   - **Node 7 (`mark_resolved`)**: Reconciles state in the session checkpointer.
3. The frontend polls or receives state via `GET /pd-sessions/{id}/live-state`, rendering dynamic cards on the officer's screen.

### Step 5: ChromaDB RAG Benchmark Matching
1. During gap analysis, the system queries `app/rag/retrieval.py` with the applicant's business profile (e.g. *"Kirana Store"*).
2. If exact name matching succeeds, the benchmark row is loaded directly.
3. If the officer entered a non-standard description (e.g. *"general grocery and provisions shop"*), ChromaDB executes a vector cosine similarity search across the `profession_profiles` collection to retrieve the closest matching trade profile and its checklist.

### Step 6: Officer Numeric Reconfirmations & Remarks
1. During or at the end of the interview, the officer taps the screen to reconfirm verified financial values via `POST /pd-sessions/{id}/reconfirm`.
2. The officer enters qualitative observations (market reputation, footfall, premises maintenance) via `POST /pd-sessions/{id}/remarks`.
3. Geotagged premises photos are uploaded and checked for duplicates using `app/utils/image_hash.py`.

### Step 7: Completion Gate Enforcement
1. The officer taps **"Complete PD"**, triggering `POST /pd-sessions/{id}/end-session`.
2. `app/utils/completion_gate.py` verifies all mandatory requirements:
   - Valid audio recording attached.
   - Non-empty transcript segments.
   - All core numeric fields reconfirmed.
   - Required premises photos uploaded.
   - Officer remarks submitted.
3. If any requirement is missing, submission is rejected with an explicit checklist of missing items.
4. If verified, session status becomes `COMPLETED` and application status advances to `PD_COMPLETE`.

### Step 8: Credit Assessment Memorandum (CAM) Generation
1. `app/agents/report_assembly.py` builds the comprehensive underwriting memo:
   - Injects pure deterministic math (`calculate_emi`, `calculate_foir`, `calculate_ltv`).
   - Generates Section 11 narrative via `app/agents/report_narrative.py` with tone filtering.
   - Compiles HTML template into a publication-ready PDF via WeasyPrint, saved to `uploads/reports/`.

### Step 9: Admin Quality Analytics & Proactive Leaderboard
1. Branch managers and credit administrators access the `/admin/` API:
   - `GET /admin/scores`: Review officer uptake and thoroughness.
   - `GET /admin/consistency-flags`: Review borrower contradiction risks.
   - `GET /admin/cases`: Monitor stage conversion funnels.
   - `GET /admin/leaderboard`: Rank officers by proactive diligence bonuses.
