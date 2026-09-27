# MSFincap Phase 1

See /docs for the full architecture, feature list, and data flow documents.
Backend: FastAPI + Celery + Postgres/pgvector. Frontend: Next.js.

## Running locally (MVP -- no Docker)

Everything runs directly on one machine for now, no containers:

1. Install and start PostgreSQL locally, create a database, enable the pgvector extension.
2. Install and start Redis locally.
3. Backend: cd backend, pip install -r requirements.txt, copy .env.example to .env and fill in
   your local DB/Redis URLs and LLM API key, then run 'uvicorn app.main:app --reload' and, in a
   separate terminal, 'celery -A app.workers.celery_app worker --loglevel=info'.
4. Frontend: cd frontend, npm install, npm run dev.

Containerizing this (Docker) is a later step, once the setup needs to move across environments
or scale beyond one machine -- not needed for the MVP.
