# Week 12 Monitoring Review — Working Notes

Status legend: ✅ reviewed & sound · ⚠️ real gap, not fixed this week (documented + reasoned) · 🔧 fixed this week

---

## 1. Error Tracking

**Method**: searched the codebase for any real error-tracking service
integration (Sentry or comparable), then checked what actually happens
server-side when an unhandled exception occurs, distinct from what the
client sees (already covered by the Week 12 security audit's `DEBUG`
fix).

### ⚠️ Found, not fixed this week: no error-tracking service is integrated anywhere

Confirmed by direct search: no Sentry (or comparable) SDK is a
dependency, imported, or configured anywhere in the codebase. This means
production errors have no dedicated capture, aggregation, alerting, or
searchable history — the only trace of a real failure would be whatever
appears in raw container stdout/stderr, dependent entirely on whatever
the deployment platform does with that output (which may or may not be
retained, searchable, or alertable on, and is deployment-specific
configuration this app doesn't control).

**Verified the client-facing half of this is genuinely correct** (a
direct test, not an assumption): an unhandled exception in a route
correctly returns a generic `500 Internal Server Error` to the client
with no leaked detail, confirming last week's `DEBUG=False` default fix
does what it's meant to. But confirming the client doesn't see internals
is a different question from whether anyone on the team WOULD see them
— and right now, that depends entirely on whether the deployment
platform captures and retains stdout/stderr, which is not something
this application's own code does anything to ensure.

**Not fixed this week**: adding a real error-tracking SDK (e.g. the
`sentry-sdk` package, with its FastAPI integration) is a small, safe,
genuinely low-risk addition in principle, but doing it properly requires
a real DSN/account to configure and verify against — not something this
audit can meaningfully complete without a live account, and a
half-wired integration (dependency added, but never actually verified to
capture a real error) would be worse than clearly documenting the gap.
Flagged as a concrete, specific, low-effort item for the final report:
add `sentry-sdk[fastapi]`, configure via an environment variable
(`SENTRY_DSN`, unset = disabled, same fail-open-safe pattern as
`CREDENTIALS_ENCRYPTION_KEY` is fail-closed), before accepting real
production traffic.

## 2. Application Logs

**Method**: searched for real Python `logging` module usage and
configuration across the whole codebase (not test files), and separately
checked for bare `print()` statements in request-path code.

### ⚠️ Found, not fixed this week: effectively no application-wide logging infrastructure exists

Confirmed by direct, exhaustive search: only 2 real `logging` usages
exist in the entire non-test codebase - both in `app.mail.service`
(logging instead of failing when SMTP isn't configured, a real,
reasonable Week 1 design choice already documented in that module). One
bare `print()` exists, in `app.db.seed_roles` (a one-off setup script,
not request-path code - genuinely fine as-is).

**The practical consequence**: the large majority of this app's real
work - every AI provider call, every OAuth token exchange, every Meta
Ads API call, every Celery task execution, every real business decision
an agent makes - produces zero deliberate log output anywhere. Whatever
observability exists is limited to Uvicorn's own default HTTP access
log (confirmed still enabled - `backend/Dockerfile`'s production `CMD`
doesn't disable it), which records request path/status/timing, but
nothing about what happened *inside* the request.

**Not fixed this week**: retrofitting structured logging across ~40
real service modules is genuine, substantial work - not a
one-line config fix, and doing it hastily risks either missing the
modules that matter most or introducing noisy, unhelpful logging that's
worse than none. Recorded here as a real, significant gap for the final
report, with a concrete starting-point recommendation: prioritize
structured logging (not bare `print`) at minimum for the 4 highest-value
locations - AI provider errors (`app/ai_providers/`), OAuth token
exchange failures (`app/oauth/service.py`), Meta Ads API errors
(`app/meta_ads/`), and Celery task failures (already have SOME real
signal via retry/failure status, but no log line accompanies it) -
rather than attempt a full retrofit under Week 12's time constraints.

**Not yet reviewed**: AI usage monitoring, API monitoring, background
job monitoring, campaign sync monitoring. Continuing next.
