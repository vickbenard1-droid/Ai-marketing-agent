# Week 12 Deployment Review — Working Notes

Status legend: ✅ reviewed & sound · 🔧 fixed this week · ❓ genuinely requires a real target environment / human decision, not something this audit can complete

---

## 1. Docker

✅ **Reviewed in full.** `backend/Dockerfile` and `frontend/Dockerfile`
are both genuinely well-built: multi-stage builds, non-root users, and
(as of this week's fixes) both have real `HEALTHCHECK` directives. The
frontend Dockerfile correctly handles the real Next.js build-time-vs-
runtime `NEXT_PUBLIC_*` env var distinction — a common, easy-to-get-wrong
pitfall for this framework, handled correctly and documented in the file
itself.

🔧 Fixed this week: frontend `HEALTHCHECK` was missing entirely (added,
matching the backend's proven pattern — see commit history). **Honest
limitation**: no Docker is available in this review environment, so
neither Dockerfile's `HEALTHCHECK` was verified with an actual container
build/run cycle — verified by careful inspection and by matching an
already-proven-working pattern, which is a real but different thing
from directly testing it.

## 2. docker-compose.yml (local dev)

✅ Genuinely well-built for its stated, honest scope (local development
only, explicitly documented as such in its own header comment) — real
health checks, correct service dependency ordering.

🔧 Fixed this week: its own setup instructions were missing the
`seed_plans` step (found alongside the CI gap below).

## 3. Environment Variables

🔧 **Fixed a genuinely major gap this week**: `backend/.env.example` was
missing all 13 real OAuth platform credential pairs (every platform
integration built across Weeks 6–8) plus `OAUTH_REDIRECT_BASE_URL`, and
told anyone copying it to set `DEBUG=true` — directly contradicting this
week's own security fix. Both corrected; re-verified complete via a
systematic cross-reference against the real `Settings` class (see
commit history for the full diff).

## 4. CI/CD

✅ Reviewed in full — genuinely correct as far as it's scoped: real
Postgres service container for a genuine `alembic upgrade head` dry-run
and seed-script smoke tests, real separate backend (lint/test) and
frontend (typecheck/build) jobs, test-only secrets clearly marked as
never touching real credentials.

🔧 Fixed: `seed_plans` was missing from the CI smoke-test steps
(matching the same real gap found in `docker-compose.yml`).

**What CI does NOT do, honestly noted rather than left implicit**: it
runs tests and builds on push/PR — it does not deploy anywhere. There is
no CD (continuous deployment) step at all: no build-and-push of a
container image to a registry, no deploy trigger to any hosting
platform. This is a real, correctly-scoped gap for this repository as a
codebase (deployment targets and credentials are inherently specific to
wherever this gets hosted, which this audit has no visibility into) —
recorded here as something a real launch needs to add, not something
missing from this review.

## 5. Domain Configuration & HTTPS

❓ **Genuinely requires a real target environment — not something this
audit can complete or fabricate.**

Searched the entire repository: no reverse-proxy configuration (nginx,
Caddy, Traefik), no TLS/certificate management (Certbot, ACME), and no
domain-specific configuration exists anywhere. This is not a finding
that something is broken — it's an honest statement that this layer of
infrastructure is, correctly, **not something the application codebase
itself owns**. HTTPS termination and domain routing belong to whatever
sits in front of the containers in a real deployment: a managed load
balancer, a platform's built-in TLS (e.g. a PaaS that terminates HTTPS
automatically), or a self-managed reverse proxy.

**Deliberately not fabricated this week**: writing a plausible-looking
nginx config or a specific cloud provider's TLS setup without knowing
the real target environment would create a false sense of completeness
— a config that looks right but doesn't match where this actually gets
deployed is arguably worse than clearly stating the gap. This is exactly
the kind of item that belongs in the final report's "requires manual
configuration" section: **before accepting real traffic, whoever deploys
this must configure real HTTPS termination and a real domain pointing at
both the frontend and backend (or a reverse proxy routing both under one
domain) — this is not optional for handling real user credentials and
payment-adjacent data, and is not something a code review can complete
in the abstract.**

`BACKEND_CORS_ORIGINS` (reviewed during the Week 12 security audit) also
needs real production values here — it defaults to a specific localhost
origin, safe as a default but requiring explicit configuration to the
real deployed frontend domain.

## 6. Backups

❓ **A real, significant gap — genuinely absent, not deferred to
infrastructure the way domain/HTTPS correctly is.**

Searched the entire repository for any backup strategy, scheduled
`pg_dump`/snapshot tooling, or documented restore procedure: **none
exists.** Unlike domain/HTTPS (which is legitimately infrastructure this
codebase shouldn't own), a *documented* backup and restore strategy is
something a production-readiness review should be able to point to even
without a live deployment — and this repository has nothing: no backup
schedule, no retention policy, no restore runbook, no verification that
a restore has ever been tested.

This matters more than it might first appear given what this app
stores: real business data (campaigns, leads, content), real encrypted
OAuth credentials, and (as of this week) real billing/subscription
state — losing this data with no recovery path is a genuine business
risk, not a theoretical one.

**Not fixed this week**: an actual backup implementation depends
entirely on the real target database platform (a managed Postgres
service typically has its own built-in automated backups and
point-in-time recovery — the right answer here is very likely "enable
and verify the hosting platform's own backup feature," not "write a
custom pg_dump cron job," but which is correct depends on infrastructure
this audit has no visibility into). What IS being done here: stating
this plainly and specifically for the final report as a genuine
must-address item before accepting paying customers — a business
appropriately promising customers their data is safe needs a real,
tested backup and restore procedure, and currently has none.

## Summary of Deployment Review

Real, fixable-in-code gaps found and fixed this week: a missing frontend
health check, a substantially incomplete `.env.example`, and a missing
CI/CD seed step (3 genuine fixes). Two items — domain/HTTPS and backups
— are correctly identified as requiring a real target environment or an
explicit operational decision rather than something this code-level
review can complete; both are named specifically and honestly for the
final report rather than glossed over or fabricated.
