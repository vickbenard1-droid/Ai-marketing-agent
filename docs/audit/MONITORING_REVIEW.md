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

## 3. AI Usage Monitoring

✅ **Genuinely sound, and architecturally enforced, not just followed by
convention.**

A real endpoint (`GET /ai-usage/summary`) returns real, computed
per-organization usage: total/successful/failed calls, real input/output
token totals, a real computed `total_estimated_cost_usd` (not a
placeholder), and a breakdown by source.

**Verified this is architecturally impossible to bypass, not just
usually followed**: confirmed `app.ai_usage.service.generate_and_track`
is the *only* place in the entire codebase that calls a provider's
`.generate()` method directly — its own docstring states this is
deliberate ("so no call site can forget to log usage"). Cross-checked
all 15 real call sites that obtain a provider instance
(`get_ai_provider_for_task`) across every AI-generating module built
across all 11 weeks (content generation, campaign generation, SEO,
chat, the orchestrator's planner, every one of the 7 spec agents that
make their own AI call, the sales agent, lead follow-up) — every one
routes through the single tracked wrapper. No AI usage in this app can
occur without being recorded.

## 4. Background Job Monitoring and Campaign Sync Monitoring

**Method**: checked whether the real per-attempt records these systems
already produce (`PublishingLog` for Week 6 publishing,
`OptimizationDecision`/`AgentActivityLog` for Week 9/11) are actually
surfaced anywhere observable, and separately, whether the Week 7/8 Meta
Ads sync functions are reachable from anywhere in the real application
at all — a more fundamental question than "is it monitored."

✅ **Scheduled post publishing has real, genuine observability at the
per-post level.** `GET /scheduled-posts/{id}` (`ScheduledPostDetail`)
includes the real `publishing_logs` history for that post — every
attempt, its outcome, real data, not a stub. No dedicated org-wide "show
me every failed publish across all posts" view exists, but the
underlying data and a real per-post drill-down both genuinely exist.

✅ **The optimization agent's scan is genuinely observable.** `POST
/meta-ads/meta-campaigns/{id}/scan` triggers a real, on-demand scan
(tested this week), and its results are real `OptimizationDecision`
rows, visible via `GET /optimization/decisions` — real monitoring exists
here, on-demand rather than scheduled (see Section 2 of the Performance
review for the scheduling gap itself).

### ⚠️ Found, not fixed this week: the Meta Ads analytics sync (Week 8) is not just unmonitored — it is currently unreachable from anywhere in the deployed application

This is a more fundamental finding than a monitoring gap. Confirmed by
exhaustive search: `app.analytics.sync_orchestrator.
sync_meta_insights_for_organization` and `app.meta_ads.sync_service`'s
`sync_campaign_status`/`sync_insights` have **zero callers anywhere in
the real application** — no API endpoint, no Celery task, nothing.
These are real, correct functions (verified extensively via direct
function calls during their original Week 7/8 build and again during
this audit's own performance measurements), but as currently deployed,
**Meta Ads analytics data never actually syncs into `MetricSnapshot` at
all** — the unified analytics dashboard, the sales agent, and the
optimization agent's own signal evaluation would all be working from
permanently stale (in practice, entirely empty, since nothing ever
populates it) data in a real deployment, regardless of the scheduling
question raised in the Performance review.

**This materially changes, and should replace, part of what Section 2
of the Performance review said**: that section correctly identified "no
Beat schedule exists" as the gap; this finding is more specific and more
severe for this one case specifically — there isn't even a manual
trigger to schedule in the first place. **Fixing this requires two
things, not one**: (1) exposing sync as a real, callable action (at
minimum an on-demand API endpoint, matching the pattern the optimization
scan already correctly has), and (2) separately, scheduling it to run
automatically (the Beat gap). Both are real, necessary, and distinct
pieces of missing work.

**Not fixed this week**: same reasoning as every other Monitoring/
Performance finding — this is real new functionality (wiring an
endpoint or task to genuinely unreachable, if correct, business logic),
not a hardening fix, and deserves to be built and tested properly rather
than added hastily this late in the week. Flagged as a concrete,
specific, and now correctly-characterized-as-more-severe item for the
final report: **the Meta Ads analytics sync must be wired to a real
trigger (on-demand endpoint at minimum, scheduled execution for real
production use) before this app's analytics/sales/optimization features
can be considered functional against real, current data in production.**

