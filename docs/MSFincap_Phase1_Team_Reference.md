# MSFincap Phase 1 — Team Reference
### For Shashwat, Riddhi, and anyone joining the project

This is the single document that explains everything about Phase 1 — what it does, why every decision was made, what data it collects, and how it all fits together. If you're new to the project, read this top to bottom before touching code.

---

## 1. What Phase 1 Is, In One Paragraph

A loan officer visits a borrower in person, conducts a structured interview (recorded, guided by tiered questions), takes photos of the business/residence, and the system automatically transcribes, analyzes, and cross-checks everything — flagging gaps, contradictions, and anything needing officer follow-up — before assembling it all into a final PD report. Phase 1 stops there; it doesn't score credit risk or decide whether to approve the loan. That's Phase 2.

---

## 2. Full Feature List (everything Phase 1 does)

1. **Case intake** — applicant details, OTP-verified phone, product/loan details.
2. **Tiered questioning** — Tier 1 (universal), Tier 2 (self-employed vs. salaried), Tier 3 (specific business/employer category).
3. **In-person recording** — audio captured via the browser during the visit, no phone-call step.
4. **Automatic transcription** — speech-to-text on the recording, with confidence scoring.
5. **AI-driven gap analysis (RAG), multi-round** — the transcript is compared against a professionally-authored reference document for that specific business type (one of 20-25 documents), and the system suggests follow-up questions the officer should still ask. This isn't a single pass — after the officer answers a round of suggested questions, the system re-checks and generates another round if gaps remain, continuing **until every required item on that profession's checklist is covered, or the officer ends the visit** — whichever happens first. There's no fixed number of rounds; it's driven entirely by whether the checklist is actually complete.
6. **Numeric reconfirmation** — any income/rate/amount figure pulled from audio is shown back to the officer to confirm out loud with the borrower before it's trusted.
7. **Photo capture with per-photo GPS** — every photo carries its own location and timestamp, used to confirm the officer was actually where they claim to be.
8. **Vision analysis** — photos are analyzed for fixed details (machinery type, count, condition) via an AI vision model.
9. **Customer consistency scoring** — if the borrower's story changes mid-conversation (e.g., states income two different ways), it's automatically flagged with both values and when each was said.
10. **Officer scoring** — the officer's own performance on that PD is scored, based on question coverage, whether they acted on the AI's suggestions, and whether they properly reconfirmed flagged figures.
11. **Officer remarks** — a structured space for the officer to respond to specific flags, plus a genuine open field for anything else they noticed.
12. **EMI calculator** — an interactive tool in the officer's app for discussing affordability live with the borrower.
13. **Automatic FOIR/LTV calculation** — computed in the background the moment income is confirmed, shown in the final report.
14. **Completion gate** — a case can't be marked complete with any mandatory field, required photo, or unresolved question missing.
15. **PD report generation** — everything above assembled into MSFincap's own report format (template pending), including a Customer Response section (transcript or summary).
16. **Admin panel** — analytics on officer performance, consistency-flag trends, and case progress, shown as graphs.

**Deliberately not in Phase 1:** land valuation, phone-call-based PD, a separate native mobile app, credit scoring/CIBIL/CAM generation (Phase 2), and a custom-trained vision model (using a general AI vision model instead for now).

---

## 3. Every Data Point Phase 1 Collects or Produces

| Category | Data points |
|---|---|
| **Applicant** | Name, phone, PAN, Aadhaar number, employment type, business category, employer type |
| **Application** | Product type, requested amount, tenure, rate, status |
| **PD Session** | Recording, consent timestamp, full transcript, per-segment confidence |
| **Extracted fields** | Every Tier 1-3 answer, tagged as stated / inferred / not-captured, with officer-confirmed flag on numerics |
| **Gap questions** | AI-suggested follow-ups, whether asked, the answer given |
| **Photos** | Category, GPS (per photo), timestamp, AI-extracted machinery/count/condition |
| **Officer score** | Coverage %, suggestion uptake %, reconfirmation diligence, overall score |
| **Customer consistency** | Flagged field, both conflicting values, when each was said, severity, resolution |
| **Officer remarks** | Structured response per flag, open-ended observations |
| **Calculations** | EMI, FOIR %, LTV % (or status if not applicable) |

Every one of these fields either has a confirmed value, an explicit "not available" marker, or a flag requiring review — nothing is ever silently ambiguous by the time a case is complete.

---

## 4. Architecture (the six layers)

1. **Client layer** — one Next.js app, responsive for both desktop and mobile browser use (no separate native app); a separate Admin Panel section for analytics.
2. **Backend layer** — FastAPI (single service) + Celery/Redis for anything AI-related, so the officer's screen never freezes waiting on a model call.
3. **Agent processing layer** — five agents, run in a fixed sequence per case:
   - Speech-to-Text (`faster-whisper`, self-hosted)
   - Classify + RAG (identifies business type, retrieves the matching reference doc, finds gaps)
   - Vision + GPS Confirmation (analyzes photos, checks photo locations are consistent)
   - Officer Scoring Agent
   - Customer Consistency Agent
4. **External services** — only two things ever leave MSFincap's own servers: the LLM API call (Groq/Gemini free tier, for text and vision) and a maps/geocoding lookup. Everything else — audio, transcripts, photos — stays in-house.
5. **Database & storage** — PostgreSQL (with the pgvector extension doing double duty as the vector store for the 20-25 reference documents) and file storage for recordings/photos/reports. For MVP, everything runs directly on one machine — Postgres, Redis, and the app processes installed natively, no Docker/containers yet. That's a later step, once the setup needs to move across environments or scale beyond one box.
6. **Calculation & report layer** — the EMI/FOIR/LTV calculator (pure math, no AI) and the Report Assembly Agent that produces the final PD report.

A seventh area is marked as a **future integration point, not built yet**: Phase 2 (bureau/CIBIL data, credit scorecard, CAM generation) will sit downstream and consume Phase 1's clean output directly.

*(See the accompanying architecture diagram and file-structure document for the visual and code-level breakdown.)*

---

## 5. Why Key Decisions Were Made

- **Web app only, no Tele-PD:** doing PD entirely in person removes an entire subsystem (call recording, consent-before-call, a whole extra fraud surface for remote-only interviews) for a small team to maintain, at the acceptable cost of not being able to pre-screen borrowers remotely.
- **Multiple rounds of AI follow-up questions, but not live/real-time:** live nudging (whispering questions to the officer *while the borrower is still talking*) needs streaming transcription and sub-second inference — a serious infra investment we're skipping. What we do instead is cheaper but still thorough: after each round of answers, the system pauses, re-checks the profession checklist, and generates another round if gaps remain — repeating for as many rounds as it actually takes, with **no fixed cap on the number of rounds**. The natural stopping point is either the checklist being fully covered, or the officer ending the visit. If the officer ends the session with checklist items still open, that counts directly against their coverage score — so there's real pressure to actually close the gaps, without the system ever forcing a session to drag on artificially.
- **Vision-LLM instead of YOLO:** YOLO only recognizes what it's trained on, and there's no labeled photo dataset yet. A general vision-LLM works today with zero training data; a custom YOLO model can be added later once enough real field photos exist to train on.
- **Officer scoring and customer consistency scoring are kept as two separate numbers, never merged:** a customer changing their story isn't the officer's fault — unless the officer fails to notice or resolve it, which is captured separately in the officer's diligence score. Merging them would unfairly penalize an officer for their borrower's behavior.
- **GPS is tied to every photo, not one reading per visit:** a single GPS reading at the start of a visit can be spoofed once and then ignored. Requiring every photo to carry its own consistent location is much harder to fake across many photos than once.
- **Land valuation engine removed:** simplifies Phase 1's scope; can be reintroduced later as its own explicitly-scoped module if/when needed for LAP cases.
- **Officer remarks are structured, not a blank box:** a free-text field with no prompt tends to produce low-effort answers (a real example from a competitor's product: an officer wrote nothing more useful than "business is too good"). Forcing the officer to respond to specific system-raised flags, while still keeping a genuinely open field for anything else, gets real judgment without the low-effort failure mode.
- **pgvector instead of a separate vector database:** for 20-25 documents, adding a whole separate database system is unnecessary infrastructure for a 2-person team. One Postgres instance does both jobs.
- **Free-tier hosted LLMs instead of self-hosting the model itself:** self-hosting speech-to-text is lightweight and worth doing in-house; self-hosting a full LLM well is a much bigger undertaking better deferred until volume or privacy needs justify it. The LLM call is isolated behind one code interface specifically so this can change later without a rewrite.

---

## 6. What "Done" Looks Like for Phase 1

A case is fully built and working when: an officer can create a case, conduct the full tiered interview with live recording, receive AI-suggested follow-up questions and act on them, reconfirm every flagged number, capture GPS-verified photos, see any customer inconsistency surfaced and add their own remarks, and submit — at which point the system blocks incomplete submissions, computes EMI/FOIR automatically, scores the officer's performance on that PD, and generates a complete PD report ready to be handed to Phase 2.

---

## 7. Where to Go Next

- **`MSFincap_Phase1_AI_Agent_Build_Context.md`** — the exact technical specification (schemas, API endpoints, agent logic, formulas) for actually building this.
- **File structure document** — the proposed codebase layout, one file per responsibility.
- **Architecture diagram (SVG)** — the visual layer breakdown.
- **Data flow worked example** — a full case walked through step by step with real example numbers.
