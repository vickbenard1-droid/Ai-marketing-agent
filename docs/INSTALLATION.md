# Installation Guide

This guide gets a real, working local instance of the AI Marketing
Agent running. Every command here is verified against the actual files
in this repository as of Week 12 — not aspirational instructions.

## Prerequisites

- Docker and Docker Compose (for the local dev stack — see
  `docker-compose.yml`)
- Node.js 20+ (only needed if you want to run the frontend outside
  Docker; matches `frontend/Dockerfile`'s base image)
- Python 3.12+ (only needed if you want to run the backend outside
  Docker; matches `backend/Dockerfile`'s base image)

## 1. Clone and configure environment variables

```bash
git clone <this repository>
cd ai-marketing-agent
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Open `backend/.env` and fill in, at minimum:

- `SECRET_KEY` — generate one: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `CREDENTIALS_ENCRYPTION_KEY` — generate one: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  (the app fails to start without this — see `app/core/security.py`)
- `ANTHROPIC_API_KEY` — required for any AI-generating feature (content,
  campaigns, the orchestrator, every agent) to work; the app runs fine
  without it for everything else

Every other variable in `backend/.env.example` is optional for local
development. The OAuth platform credential pairs (Facebook, LinkedIn,
Meta Ads, Google Ads, etc.) only need to be filled in for the specific
platforms you want to actually connect to during testing — a platform
with no credentials configured is simply unavailable to connect, with a
clear error, not a broken handshake.

`frontend/.env.example` only has one real variable
(`NEXT_PUBLIC_API_URL`), already pointed at the local backend by
default.

## 2. Start the local stack

```bash
docker compose up
```

This starts Postgres, Redis, the backend API, the Celery worker, and
the frontend, in the correct dependency order (real health checks gate
startup — see `docker-compose.yml`).

## 3. Seed the database and run migrations (first run only)

```bash
docker compose exec backend python -m app.db.seed_roles
docker compose exec backend python -m app.db.seed_plans
docker compose exec backend alembic upgrade head
```

Both seed scripts are idempotent — safe to re-run.

## 4. Verify it's working

- Backend health check: `curl http://localhost:8000/health` should
  return `{"status": "ok", ...}` (a real check — it fails with a 503 if
  the database connection is broken, not just a liveness ping)
- Frontend: open `http://localhost:3000`
- Register a real account through the frontend, or directly:
  ```bash
  curl -X POST http://localhost:8000/api/v1/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"you@example.com","password":"supersecret123","full_name":"You","organization_name":"My Business"}'
  ```

## Running the backend test suite (no Docker required)

```bash
cd backend
pip install -r requirements.txt
export SECRET_KEY=testkey CREDENTIALS_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") DATABASE_URL=sqlite:///:memory: APP_ENV=test
python -m pytest app/tests -q
```

The test suite always uses an in-memory SQLite database regardless of
`DATABASE_URL` (see `app/tests/conftest.py`) — no real database or
Docker is needed to run it. As of Week 12, this is 266 tests; see
`docs/audit/TESTING_SUMMARY.md` for what's covered and what isn't.

## Running the end-to-end simulation

```bash
cd backend
python -m app.tests.e2e_simulation
```

Simulates a complete real customer journey (register through
generating a report) via real HTTP requests against a real running
instance of the app. See `docs/audit/DEPLOYMENT_REVIEW.md` and the
final production-readiness report for what this does and doesn't prove.

## Common issues

- **"CREDENTIALS_ENCRYPTION_KEY is not set" on startup** — this is a
  deliberate fail-closed check (`app/core/security.py`); generate a real
  key as shown above, don't leave it blank.
- **AI-generating features return "ANTHROPIC_API_KEY is not
  configured"** — expected if you haven't set a real key; every other
  feature works without it.
- **A platform "isn't available to connect"** — expected if that
  platform's OAuth credentials aren't set in `backend/.env`; fill in
  only the platforms you need.
