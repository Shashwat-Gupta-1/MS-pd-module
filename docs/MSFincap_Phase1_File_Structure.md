# MSFincap Phase 1 — Project File Structure

This is the proposed repository layout — one file per responsibility, so any bug can be traced to exactly one place. A ready-to-unzip skeleton with all these files already created (each with a header comment describing its job) is attached alongside this document as `msfincap-phase1-skeleton.zip`.

```
msfincap-phase1/
├── README.md                                    # how to run postgres+pgvector, redis, backend, frontend locally — no Docker for MVP
│
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   │
│   ├── alembic/                                 # DB migrations — run after every model change
│   │   └── versions/
│   │
│   └── app/
│       ├── main.py                              # FastAPI app entrypoint, registers all routers
│       │
│       ├── core/
│       │   ├── config.py                        # env-based settings (DB, Redis, LLM keys, JWT secret)
│       │   ├── security.py                      # JWT, password hashing, OTP, role checks
│       │   └── database.py                      # SQLAlchemy engine/session/Base
│       │
│       ├── models/                              # one SQLAlchemy model per table
│       │   ├── officer.py
│       │   ├── applicant.py
│       │   ├── application.py
│       │   ├── question_bank.py
│       │   ├── pd_session.py
│       │   ├── transcript_segment.py
│       │   ├── extracted_field.py
│       │   ├── gap_question.py
│       │   ├── ground_pd_photo.py
│       │   ├── photo_extraction.py
│       │   ├── officer_pd_score.py
│       │   ├── customer_consistency_flag.py
│       │   ├── bre_preliminary_calc.py
│       │   └── officer_remark.py
│       │
│       ├── schemas/                             # Pydantic request/response, mirrors models/
│       │   ├── applicant.py
│       │   ├── application.py
│       │   ├── auth.py
│       │   ├── bre_preliminary_calc.py
│       │   ├── customer_consistency_flag.py
│       │   ├── extracted_field.py
│       │   ├── gap_question.py
│       │   ├── ground_pd_photo.py
│       │   ├── officer_pd_score.py
│       │   ├── officer_remark.py
│       │   ├── pd_session.py
│       │   ├── photo_extraction.py
│       │   └── question_bank.py
│       │
│       ├── api/
│       │   ├── deps.py                          # shared deps: get_db, get_current_user
│       │   └── routes/
│       │       ├── auth.py                      # login, OTP verification
│       │       ├── applicants.py                # applicant intake
│       │       ├── applications.py              # case CRUD, submit-pd
│       │       ├── questionnaire.py             # Tier 1-3 question lookup
│       │       ├── pd_sessions.py               # recording, gap-resolve, reconfirm
│       │       ├── ground_pd.py                 # photo upload
│       │       ├── reports.py                   # PD report generation/retrieval
│       │       └── admin.py                     # question-bank config, analytics endpoints
│       │
│       ├── agents/                              # every AI agent, one file each
│       │   ├── llm_client.py                    # isolated LLM interface — swap providers here only
│       │   ├── embeddings.py                    # sentence-transformers wrapper
│       │   ├── speech_to_text.py                # Agent 1
│       │   ├── classify_rag.py                  # Agent 2
│       │   ├── vision_extraction.py             # Agent 3 (+ GPS confirmation)
│       │   ├── officer_scoring.py               # Officer Scoring Agent
│       │   ├── customer_consistency.py          # Customer Consistency Agent
│       │   └── report_assembly.py               # Report Assembly Agent
│       │
│       ├── workers/
│       │   ├── celery_app.py                    # Celery instance config
│       │   └── tasks.py                         # task wrappers around each agent
│       │
│       ├── calculations/
│       │   └── emi_foir_ltv.py                  # pure deterministic math, no AI, heavily unit-tested
│       │
│       ├── rag/
│       │   ├── ingest_profession_docs.py        # one-off: load the 20-25 profession docs into pgvector
│       │   └── retrieval.py                     # similarity search given a business category
│       │
│       ├── utils/
│       │   ├── gps_utils.py                     # distance calc, cluster-tightness check
│       │   ├── image_hash.py                    # duplicate photo detection
│       │   ├── pii_masking.py                   # auto-mask before wide-circulation reports
│       │   └── completion_gate.py               # the hard stop before PD_COMPLETE
│       │
│       └── tests/
│           ├── test_applications.py
│           ├── test_calculations.py             # verifies EMI/FOIR/LTV against known examples
│           ├── test_customer_consistency.py
│           └── test_completion_gate.py
│
└── frontend/
    ├── package.json
    ├── app/
    │   ├── officer/
    │   │   ├── new-case/page.tsx                # Screen 1: Create Case
    │   │   └── cases/[id]/
    │   │       ├── questionnaire/page.tsx       # Screen 2: Tier 1-3 + recording
    │   │       ├── gap-questions/page.tsx       # Screen 4: AI follow-ups + consistency flags
    │   │       ├── reconfirm/page.tsx           # Screen 5: numeric reconfirmation
    │   │       ├── photos/page.tsx              # Screen 6: photo capture
    │   │       └── review/page.tsx              # Screen 7: review, remarks, EMI calc, submit
    │   │
    │   └── admin/
    │       ├── dashboard/page.tsx               # case funnel overview
    │       ├── officers/page.tsx                # per-officer score analytics
    │       └── analytics/page.tsx               # consistency-flag trends, portfolio-wide
    │
    ├── components/
    │   ├── QuestionnaireForm.tsx
    │   ├── RecorderWidget.tsx                   # MediaRecorder wrapper + consent gate
    │   ├── CameraCapture.tsx                    # Camera + Geolocation wrapper
    │   ├── GapQuestionsList.tsx
    │   ├── EMICalculator.tsx                    # standalone, client-side only
    │   ├── ConsistencyFlagBanner.tsx
    │   ├── OfficerRemarksForm.tsx
    │   └── AnalyticsChart.tsx                   # Recharts wrapper, reused across admin pages
    │
    ├── lib/
    │   ├── api.ts                               # typed fetch wrapper
    │   └── types.ts                             # TS types mirroring backend schemas
    │
    └── styles/
        └── globals.css
```

**Design principle behind this layout:** every table has exactly one model file and one schema file; every agent has exactly one file; every screen has exactly one page file. If something is broken, the bug lives in one predictable place — you should never have to search across multiple files to find where a given piece of logic lives.

**Not yet included (add when Phase 2 is scoped):** a `phase2/` directory for bureau/CIBIL integration, scorecard logic, and CAM generation — kept out entirely for now so Phase 1's structure doesn't need to change when that work begins; it will import from `models/`, `schemas/`, and the existing `applications` table rather than requiring changes to Phase 1 code.
