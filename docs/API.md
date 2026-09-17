# API Documentation

## Live, authoritative reference

The full, always-accurate API reference is the app's own generated
OpenAPI schema — every request/response shape, every real route, kept
automatically in sync with the actual code (unlike hand-written API
docs, which drift):

- Interactive docs: `http://localhost:8000/docs` (Swagger UI)
- Raw schema: `http://localhost:8000/openapi.json`

As of Week 12, the real schema has **115 routes across 27 route
groups** (verified directly against a running instance, not counted by
hand): `agents`, `ai-usage`, `analytics`, `auth`, `billing`,
`business-profile`, `campaigns`, `chat`, `connected-accounts`,
`content`, `content-assets`, `content-generation`, `dashboard`,
`experiments`, `health`, `leads`, `members`, `meta-ads`, `onboarding`,
`optimization`, `orchestrator`, `organizations`, `projects`, `roles`,
`scheduled-posts`, `tracking`, `users`.

This document covers the real, cross-cutting conventions every one of
those routes follows — the things worth knowing before reading the
generated schema, not a duplicate of it.

## Authentication

Bearer JWT in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Obtained from `POST /api/v1/auth/register` or `POST /api/v1/auth/login`
(both return `access_token` and `refresh_token`). Refresh via
`POST /api/v1/auth/refresh`. Access and refresh tokens are structurally
distinct — a refresh token cannot be used as an access token (see
`docs/SECURITY.md`).

## Organization context

Every tenant-scoped endpoint additionally requires:

```
X-Organization-Id: <organization uuid>
```

The caller must be a real member of that organization — this is
enforced server-side against the database on every request, never
trusted from the header alone (verified exhaustively across all routes
during the Week 12 security audit — see `docs/audit/SECURITY_AUDIT.md`).
Get your organization ID from `GET /api/v1/organizations` (lists only
organizations you're actually a member of).

## Error responses

| Status | Meaning |
|---|---|
| `400` | Invalid request state (e.g. trying to generate content for a campaign that isn't in the right status) |
| `401` | Missing or invalid authentication |
| `403` | Authenticated, but lacking the specific permission this route requires (see `app/db/seed_roles.py` for the real permission matrix per role) |
| `404` | Resource not found — including when it exists but belongs to a different organization (never distinguished from a genuine 404, so a cross-tenant probe can't tell the difference) |
| `422` | Request body failed schema validation (Pydantic) |
| `429` | Rate limit or **usage limit exceeded** — as of Week 12, this status is also used for the real billing usage-limit system (`app/billing/service.py`); the response `detail` distinguishes which |
| `502` | An upstream AI provider call failed |
| `503` | `/health` reporting the database is genuinely unreachable |

## Rate limits

A global default of 100 requests/minute per IP applies to every route
without an explicit stricter limit (auth and public tracking endpoints
have tighter, dedicated limits). See `docs/SECURITY.md` for the real
gap found and fixed here this week, and its known limitation at scale.

## Pagination

Most list endpoints in this app do not paginate — they return the
organization's complete real result set (e.g. `GET /leads`,
`GET /campaigns`). This is a deliberate, current choice appropriate to
the typical real data volumes involved, not an oversight; revisit if a
real deployment's data volume changes that calculus.

## Idempotency and side effects

Endpoints that trigger a real external action (launching a Meta Ads
campaign, publishing scheduled content, executing an autonomous
optimization decision) are deliberately structured as two steps: a
`request-*` call that only ever creates a `PENDING` approval record with
zero external side effects, and a separate, explicit `execute`/`approve`
call that a human (or, for autonomous mode, a separately-gated policy)
must make. See `docs/SECURITY.md`'s "Spending controls" and "AI
security" sections for why this exists and how it's verified.

## Versioning

All routes are under `/api/v1`. There is no v2 yet; a breaking change to
this API would need a new version prefix, not an in-place change to
existing routes.
