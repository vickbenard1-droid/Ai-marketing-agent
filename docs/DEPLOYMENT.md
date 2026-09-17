# Deployment Documentation

This document is forward-looking operator guidance for deploying this
application. For the audit findings this is built on — what was
checked, what was fixed, and the exact reasoning behind what's flagged
below as still required — see `docs/audit/DEPLOYMENT_REVIEW.md`.

## Architecture

- **Backend**: FastAPI (Python), served by Uvicorn
- **Frontend**: Next.js 14
- **Database**: PostgreSQL 16 (see `docker-compose.yml`'s pinned image
  version)
- **Cache/broker**: Redis 7 — currently used ONLY as the Celery
  broker/result backend, not as an application cache (see
  `docs/audit/PERFORMANCE_REVIEW.md` Section 4 — no caching layer exists
  yet)
- **Background jobs**: Celery worker (real tasks exist for email and
  scheduled-post publishing — see "Known gap: no scheduled execution"
  below)

`docker-compose.yml` is explicitly for local development only (stated
in its own header comment) — it is not a production deployment
manifest. Its own comment names the intended real targets: frontend to
Vercel, backend to Railway/Render/AWS or similar, "per project scope."
This document does not assume one specific platform, since the real
choice depends on decisions this codebase doesn't make.

## Required environment variables

See `backend/.env.example` and `frontend/.env.example` for the complete,
verified list (kept in sync with `app.core.config.Settings` — see the
Week 12 deployment audit for how this was confirmed). At minimum, a
real production deployment must set real, non-default values for:

- `SECRET_KEY`, `CREDENTIALS_ENCRYPTION_KEY` — the app fails to start
  without these (fail-closed by design)
- `DATABASE_URL` — a real Postgres connection string
- `REDIS_HOST`/`REDIS_PORT` or `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`
- `ANTHROPIC_API_KEY` — required for every AI-generating feature
- `BACKEND_CORS_ORIGINS` — must be set to the real deployed frontend
  domain, never left at the localhost default
- `OAUTH_REDIRECT_BASE_URL` — must be set to the real deployed backend
  URL, and must exactly match the redirect URI registered in each
  connected platform's own developer dashboard
- `DEBUG` — must remain `false` (the real default) in any
  staging/production deployment; see the Week 12 security audit for
  why this matters
- Whichever OAuth platform credential pairs the deployment actually
  needs (only the platforms you intend to support require credentials)

## Database migrations

```bash
alembic upgrade head
```

Every migration in this repository has been verified with a real
offline `--sql` dry-run in both directions before being merged — see
commit history for each migration's own verification. Run this after
deploying a new version, before traffic is routed to it.

## Seeding

```bash
python -m app.db.seed_roles
python -m app.db.seed_plans
```

Both are idempotent — safe to run on every deploy, not just the first.

## Health checks

- `GET /health` on the backend genuinely checks database connectivity
  (a real `SELECT 1`, not just a liveness ping) and returns `503` on
  failure — configure your orchestration platform's health check
  against this endpoint specifically, not just "is the process running."
- The frontend has a container-level `HEALTHCHECK` (checks the root
  page responds) — see `frontend/Dockerfile`.

## Known gaps that must be addressed before production traffic

These are carried over directly from `docs/audit/PERFORMANCE_REVIEW.md`
and `docs/audit/MONITORING_REVIEW.md` — restated here as deployment
requirements, not just findings:

1. **Worker concurrency.** The backend's production command
   (`uvicorn app.main:app`) runs a single worker process by default,
   and every AI-generating endpoint calls the AI provider synchronously
   inside the request cycle (up to a real 60-second timeout in the
   worst case). Deploy with multiple worker processes (e.g. Gunicorn
   managing multiple Uvicorn workers) before accepting real concurrent
   traffic — a single slow AI call should not be able to stall every
   other request for every organization.

2. **Rate limiter storage.** If you scale to multiple worker processes
   or multiple instances (item 1, or horizontal scaling), the rate
   limiter must also move from its current in-memory storage to a
   Redis-backed store — otherwise the effective rate limit silently
   becomes `configured_limit × worker_count`, undoing the Week 12
   rate-limiting fix. These two changes must be made together.

3. **No scheduled/periodic execution exists.** There is no Celery Beat
   schedule anywhere in this codebase. Without one, scheduled social
   posts will never actually publish on their own, and — more
   seriously — the Meta Ads analytics sync (`app.analytics.
   sync_orchestrator`) has **no trigger at all**, not even an on-demand
   one; analytics data will never populate. Before relying on
   analytics, sales reporting, or the optimization agent's automated
   scanning in production, either add a Celery Beat schedule or wire an
   equivalent external cron against the relevant internal
   endpoints/functions.

4. **No error tracking or application logging.** No Sentry (or
   comparable) integration exists, and only 2 real logging call sites
   exist in the entire backend. A production incident currently has no
   dedicated capture beyond raw container stdout/stderr. Add a real
   error-tracking SDK (configured via an env var, unset = disabled)
   before accepting real traffic.

5. **HTTPS and domain configuration are not in this codebase.** This is
   expected and correct — this layer belongs to whatever sits in front
   of the containers (a managed load balancer, a platform's built-in
   TLS, or a reverse proxy you configure). It must be set up as part of
   deployment; there is nothing to review in the application code for
   this item.

6. **No backup strategy exists.** No scheduled database backup, no
   retention policy, no tested restore procedure. Enable and verify
   your hosting platform's own managed backup feature (the likely right
   answer for a managed Postgres service) before storing real customer
   data. This is a genuine must-address item, not optional — see
   `docs/audit/DEPLOYMENT_REVIEW.md` Section 6 for the full reasoning.

## CI/CD

`.github/workflows/ci.yml` runs backend lint/tests and frontend
typecheck/build on every push and PR, against a real Postgres service
container (for a genuine `alembic upgrade head` dry-run and seed-script
smoke test — not for the test suite itself, which always uses an
in-memory SQLite database regardless).

**CI does not deploy anywhere.** There is no CD step — no image
build-and-push to a registry, no deploy trigger. Adding this is a real,
correctly-scoped next step for whichever hosting platform you choose,
not something missing from this repository as a codebase.
