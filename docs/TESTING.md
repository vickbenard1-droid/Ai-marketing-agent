# Testing

## Backend

Tests run against an **in-memory SQLite** database, not Postgres — see
`app/tests/conftest.py`. This keeps the suite fast and dependency-free for
local development. SQLAlchemy's Postgres-specific types
(`postgresql.UUID`, `postgresql.ENUM` used inside `sa.Enum` columns) degrade
gracefully on SQLite, so the same models are used unmodified.

**What this means in practice:** SQLite doesn't enforce Postgres `ENUM`
constraints the same way, and doesn't test Postgres-only behavior (e.g. the
exact `ON DELETE RESTRICT` error shape). CI (`.github/workflows/ci.yml`)
additionally runs a real `alembic upgrade head` against a live Postgres
service container before running the suite, which catches migration/DDL
issues the SQLite-based tests can't.

### Running tests

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # if not already set up
pip install -r requirements.txt

pytest                              # run everything
pytest app/tests/unit               # unit tests only — no HTTP layer
pytest app/tests/integration        # integration tests — real FastAPI TestClient
pytest --cov=app --cov-report=term-missing   # with coverage
pytest -k test_register             # run tests matching a name
```

No `.env` file or running database is required — `app/tests/conftest.py`
sets `SECRET_KEY`, `CREDENTIALS_ENCRYPTION_KEY`, and `DATABASE_URL` itself
before any app module is imported.

### What's covered (81 tests)

**Week 1:**
- **`test_security.py`** — password hashing round-trip and rejection, JWT
  access/refresh token creation and decoding, garbage-token handling.
- **`test_utils.py`** — slug generation edge cases (repeated separators,
  leading/trailing separators, no-alphanumeric-input fallback).
- **`test_auth_service.py`** — registration creates a personal org with the
  `owner` role, duplicate-email rejection, slug-collision handling
  (`acme`, `acme-2`, ...), missing-seeded-roles failure, login success/
  wrong-password/unknown-email/inactive-account cases.
- **`test_auth_api.py`** — the same behaviors through the real HTTP layer
  (status codes, response shapes), plus confirming `hashed_password` never
  appears in any response body, and that an access token can't be used
  where a refresh token is required.
- **`test_organizations_api.py`** — organization listing/creation, and a
  **tenant isolation test**: registering two separate users and asserting
  neither can see the other's organization in their `/organizations` list.

**Week 2:**
- **`test_auth_service_week2.py`** (unit) — logout/revocation (including
  idempotency and garbage/wrong-type-token handling), email verification
  (valid/unknown/reused/expired token), password reset (same matrix), all
  exercised directly against the service layer.
- **`test_auth_week2_api.py`** (integration) — the same flows through real
  HTTP, including a full "simulate clicking the emailed link" pattern:
  pull the `EmailToken` row the endpoint created, overwrite its hash to a
  raw token the test controls (the real raw token only ever existed in the
  logged/sent email), then hit the verify/reset endpoint with it.
- **`test_users_api.py`** — profile get/update (including that a partial
  update doesn't clobber other fields), change-password success/failure.
- **`test_onboarding_api.py`** — profile auto-creation on first access, the
  full 10-step flow end-to-end through completion, and confirming the step
  counter never regresses when an earlier step is revisited.
- **`test_members_api.py`** — role listing, invite/role-change/removal,
  **RBAC enforcement** (a Viewer gets a real 403 attempting to invite),
  **owner-guard rules** (the only owner can't be demoted or removed), and
  tenant isolation across two organizations' member lists.
- **`test_dashboard_api.py`** — confirms every performance field is a
  genuine `0`/`None` empty state before onboarding, and that real
  onboarding data (goal, budget) appears once saved.

### Fixtures (`conftest.py`)

- `db_session` — fresh in-memory SQLite DB per test (`StaticPool` so the
  single connection is reused within a test, then disposed).
- `seeded_roles` — inserts the current `SYSTEM_ROLES` from
  `app/db/seed_roles.py` (6 roles as of Week 2) using the test session.
- `client` — a `TestClient` with `get_db` overridden to use `db_session`,
  and the rate limiter reset before each test (all `TestClient` requests
  share one fake IP, so per-IP rate limit counters would otherwise leak
  between unrelated tests within a run — this reset is test-isolation only
  and doesn't change production rate-limiting behavior).
- `APP_ENV=test` (set in `conftest.py` before any app import) makes Celery
  run tasks eagerly, in-process — `app/tasks/celery_app.py` reads this to
  set `task_always_eager`/`task_eager_propagates`. This means
  `send_email_task.delay(...)` actually executes synchronously in tests
  (through the real mail service's log-fallback path, since `SMTP_HOST`
  isn't set in the test environment either), rather than silently queuing
  and never running.

### Adding new tests

- Business logic with no HTTP concerns → `app/tests/unit/`, test the
  service function directly against `db_session`.
- Anything through the API (status codes, auth headers, tenant isolation)
  → `app/tests/integration/`, use the `client` fixture.
- Use `app.tests.conftest.unique_email()` rather than a hardcoded email in
  any test that registers a user — tests share one in-memory DB per test
  function, but hardcoded emails still invite collisions if a test is
  copy-pasted.
- For anything involving an `EmailToken` (verification, password reset),
  the raw token can't be read back from the DB (only its hash is stored —
  see `app/models/email_token.py`). Follow the pattern in
  `test_auth_week2_api.py`: generate a token with
  `generate_opaque_token()`, overwrite the stored row's `token_hash` with
  `hash_opaque_token(raw_token)`, then use `raw_token` as if it came from
  the email.


## Frontend

```bash
cd frontend
npm install
npm run type-check   # tsc --noEmit
npm run lint         # next lint
npm run build         # production build; also runs the type checker
```

There is no component/unit test runner configured yet (no Jest/Vitest/
Playwright) — this is a Week 1 gap, not a decision to skip frontend testing
permanently. `npm run build` is the current safety net: it fails on
TypeScript errors and on any page that doesn't compile.

## CI

`.github/workflows/ci.yml` runs two independent jobs on every push/PR to
`main`/`develop`:

- **backend** — spins up a real `postgres:16-alpine` service container,
  installs dependencies, runs `alembic upgrade head` against it (the real
  migration path, not the SQLite test fixture), seeds system roles, then
  runs `pytest --cov=app`.
- **frontend** — installs dependencies, runs `type-check`, `lint`, and
  `build`.

Both jobs use test-only secrets (a throwaway `SECRET_KEY` and a real but
non-production Fernet key for `CREDENTIALS_ENCRYPTION_KEY`) defined directly
in the workflow file — never real API keys or production credentials.
