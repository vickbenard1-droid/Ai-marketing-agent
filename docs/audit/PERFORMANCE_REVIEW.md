# Week 12 Performance Review — Working Notes

Status legend: ✅ reviewed & sound · ⚠️ real finding, not fixed this week (documented + reasoned) · 🔧 fixed this week

---

## 1. Database Queries

**Method**: rather than read code and guess, measured real SQL query
counts directly (via SQLAlchemy's `before_cursor_execute` event) against
real seeded data for the highest-traffic list endpoints, to catch actual
N+1 patterns rather than assume from the schema shape alone.

✅ **List endpoints returning flat data are genuinely O(1) in query
count, confirmed by direct measurement, not just by reading the response
schema**: `GET /leads` with 20 real seeded leads executed exactly 3 SQL
queries (session/auth lookup, org membership check, the list query
itself) — not 20+. `GET /optimization/decisions` with 15 real decisions:
also 3 queries. Checked every `*Public` response schema across the
codebase for fields that access a lazy-loaded relationship object (the
actual N+1 trigger for FastAPI+Pydantic `from_attributes=True` models) —
none found; every field is a plain column.

### ⚠️ Found, not fixed this week: `scan_organization` has a real, moderate-priority linear-with-campaign-count query pattern

`app.optimization.orchestrator.scan_organization` calls `db.get(MetaCampaign,
campaign_id)` inside a loop over whitelisted campaigns (one query per
campaign, not batched), and `scan_campaign` itself performs several real
rollup/lead-score queries per campaign it scans. **Measured directly with
real seeded data**: 10 whitelisted campaigns with no triggered signals
(isolating pure DB cost from AI-call cost) → 62 real SQL queries, ~6.2
per campaign, growing linearly with campaign count.

**Honest severity assessment, not overstated or dismissed**: this is a
real, genuine finding, correctly categorized as moderate rather than
critical, for two concrete reasons — (1) the whitelist is a deliberately
small, human-curated set (an organization opts specific campaigns into
autonomous scanning; this isn't every campaign an org has), and (2) for
any campaign where a signal actually triggers, the real AI decision-
generation call (a genuine network round-trip to the model provider)
will dominate wall-clock latency by orders of magnitude regardless of
whether the DB layer does 6 queries or 1 — optimizing the DB side alone
would not meaningfully change perceived performance for that (the
actually interesting) case.

**Why not fixed this week**: a real optimization here (batching the
campaign fetch via a single `WHERE id IN (...)` query, and reviewing
whether `scan_campaign`'s own internal queries can be similarly batched)
is a genuine, nontrivial refactor of core Week 9 logic that's been
running correctly and is well-tested — this late in a hardening-focused
week, the risk of introducing a real regression in exchange for a
performance gain that's bounded by whitelist size (typically small) is
a bad trade. Recorded here explicitly as a known, real, moderate-
priority optimization opportunity for the production-readiness report,
not silently left unmentioned.

**Not yet reviewed**: API response time under concurrent load,
background job performance, AI request latency/timeout handling,
caching, frontend loading. Continuing next.

## 2. Background Jobs

**Method**: read every real Celery task in the codebase in full, then
searched specifically for any Celery Beat (periodic scheduling)
configuration to determine whether any of this actually runs on a
timer, rather than assume from task existence alone.

### 🔧 Fixed a stale, actively misleading docstring

`app/tasks/celery_app.py`'s own module docstring claimed *"No real
background tasks are defined yet"* — genuinely false as of Week 6: 3
real tasks exist (`tasks.send_email`, `tasks.publish_scheduled_post`,
`tasks.check_due_posts`), confirmed by direct codebase search. Left
uncorrected, this is the kind of comment that actively misleads whoever
reads it next (a future contributor, or this exact audit, had it not
been caught) into believing less exists than actually does. Rewrote it
to accurately point to the real task locations and, more importantly,
to honestly document the actual current gap (below) rather than the
outdated one.

✅ **The 2 real task types that exist are genuinely well-engineered.**
`app.publishing.tasks.publish_scheduled_post` correctly distinguishes
retryable failures (network blips, rate limits — retried with
exponential backoff up to `MAX_RETRIES`) from non-retryable ones
(expired credentials, content the platform rejected — these fail
straight to `FAILED` for a human to address, since retrying can't fix
them). Its own docstring already documents a genuinely subtle testing
gotcha about Celery's eager mode (`task_always_eager`) that was clearly
investigated and verified directly, not assumed — a real sign of
careful original engineering, not something this audit needed to
correct.

### ⚠️ A real, significant gap: no periodic/scheduled execution exists anywhere in this app

`check_due_posts` (the task that finds due scheduled posts and
dispatches publishing for each) has its own honest docstring noting it
would be "scheduled via Celery beat in a real deployment, not
implemented here" — confirmed by direct search: **zero Celery Beat
configuration exists anywhere in this codebase.** This means, in the
app's current state, nothing runs automatically on a timer at all.

This gap is broader than just scheduled posting, and applies equally to
every week built since: **Week 8's Meta Ads analytics sync
(`app.analytics.sync_orchestrator`) and Week 9's optimization agent scan
(`app.optimization.orchestrator.scan_organization`) also have no
recurring execution** — both are real, working, well-tested functions,
but both currently only run synchronously, on-demand, when a person (or
an external system) makes a real API request that triggers them. There
is no "check every few minutes/hours automatically" mechanism built for
any of these three real, genuinely recurring business needs (publish
scheduled content on time, keep synced analytics data fresh, let the
optimization agent actually watch campaigns continuously the way its own
name implies).

**Practical consequence if deployed as-is**: scheduled social posts
would never actually publish on their own; analytics data would only
ever be as fresh as the last time someone opened the dashboard (which
doesn't itself trigger a sync — a separate, real gap, see below);
autonomous campaign optimization would only run when someone visits the
Optimization page and clicks "scan now," which defeats much of the
point of Week 9's own automation design.

**Not fixed this week**: setting up Celery Beat (or an equivalent —
e.g. a simple external cron hitting authenticated internal endpoints) is
real infrastructure work, not a hardening fix to existing behavior, and
is exactly the kind of thing the spec's Deployment section (not
Performance) should own. Documented here in full, with the specific real
functions that need scheduling named explicitly, so the production-
readiness report can state plainly that this is required before relying
on any of this app's automation running unattended.

**Separately worth noting**: even once Beat scheduling exists, the
analytics dashboard itself has no auto-refresh/webhook-driven sync
trigger on the read side either — a person opening `/analytics` sees
whatever `MetricSnapshot` rows already exist, computed by whenever sync
last ran, not a live pull. This is a reasonable, common pattern (compute
once on a schedule, serve cached reads fast) but is worth stating
explicitly rather than leaving "the dashboard shows real-time data" as
an unstated assumption a reader might otherwise make.

**Not yet reviewed**: API response time under concurrent load, AI
request latency/timeout handling, caching, frontend loading. Continuing
next.

## 3. AI Request Latency and Worker Concurrency

**Method**: read the real AI provider client's timeout/error handling in
full, then traced whether any AI-generation call site offloads the
actual external API call to a background task (Celery) or runs it
synchronously inside the request-response cycle, then checked the real
production server command to understand actual concurrency capacity —
each step verified against real code/config, not assumed from the
others.

✅ **The AI provider client's own request handling is genuinely sound**:
a real, explicit 60-second `httpx` timeout, and a proper distinct
exception hierarchy (`AIProviderTimeoutError`, `AIProviderAuthError`,
`AIProviderRateLimitError`, `AIProviderResponseError`) rather than one
generic catch-all, plus defensive parsing of the response shape itself.

### ⚠️ Found, not fixed this week: single Uvicorn worker + fully synchronous AI calls is a real production capacity risk

Confirmed by direct search: **no AI-generation call site anywhere in
this app offloads the external AI API call to a background task** —
content generation, campaign generation, orchestrator planning, the
sales agent, and the optimization decision engine all call the AI
provider synchronously, inside the request-response cycle, meaning a
real web worker is held for the full duration of that external call
(up to the real 60-second timeout in the worst case).

Checked the real production server command (`backend/Dockerfile`'s
default `CMD`) to see how much that matters in practice: **`uvicorn
app.main:app --host 0.0.0.0 --port 8000`, with no `--workers` flag at
all** — Uvicorn defaults to a single worker process. Confirmed
`gunicorn` (the standard production pattern for running multiple Uvicorn
worker processes) isn't even in `requirements.txt`.

**Combined, honestly assessed**: as currently configured, one slow or
hanging AI request (a real, not-hypothetical scenario — model provider
latency spikes happen) can genuinely stall every other request to the
entire backend, for every organization, for up to a minute. This is a
real, significant production risk, not a theoretical one — everything
else this app does (browsing leads, checking analytics, approving a
campaign) would appear to hang for any user, anywhere, while one AI call
elsewhere is slow.

**Why not fixed this week**: the correct, standard fix (Gunicorn managing
multiple Uvicorn workers, or moving AI generation calls to Celery tasks
the way email/publishing already correctly do) is genuine infrastructure
work — adding a new dependency and changing the production run command
at minimum, more invasively restructuring several AI call sites at
worst. Given Week 12's explicit framing (harden what exists, don't add
major new architecture) and that this specific fix deserves real load
testing before being trusted, it's recorded here in full rather than
patched hastily. This is flagged as a genuine must-address item in the
Deployment section of the final report, not silently left as an
implementation detail — a single-worker production deployment of this
app should be considered NOT production-ready for real concurrent
traffic until addressed.

**Not yet reviewed**: caching, frontend loading. Continuing next.

## 4. Caching

**Method**: searched the entire application codebase for any real
caching usage (Redis client calls, `lru_cache`, `cachetools`, or any
comparable pattern) beyond the config layer and Celery's own broker/
result-backend wiring, to determine whether caching genuinely exists
anywhere versus is only referenced in configuration.

### ⚠️ Found, not fixed this week: no application-level caching exists anywhere, and this connects directly to the worker-concurrency finding above

Confirmed by direct codebase search: `REDIS_URL`/`REDIS_HOST` etc. are
configured, and Redis is genuinely used as the Celery broker and result
backend — but **nothing in the application ever uses Redis (or any
other cache) to actually cache a computed value**. Every request that
computes something non-trivial (analytics rollups, the sales agent's
data assembly, `app.orchestrator.memory.get_relevant_memory`) recomputes
it fully from the database on every single call, even for two identical
requests seconds apart.

**A genuine, worth-stating connection to the AI/worker-concurrency
finding (Section 3)**: `app/core/rate_limit.py`'s own docstring already
honestly admits its limiter is in-memory ("fine for local dev this
week"). Directly confirmed slowapi's real default storage backend is
`MemoryStorage` — genuinely per-process, not shared. This means if
Section 3's fix (multiple Uvicorn/Gunicorn worker processes) is applied
*without* also switching the rate limiter to Redis-backed storage, the
*effective* rate limit silently becomes `configured_limit ×
worker_count` — a real, easy-to-miss regression where fixing one real
problem (worker concurrency) would quietly weaken another already-fixed
one (the rate-limiting gap closed earlier this week) unless both are
addressed together. Recording this connection explicitly here so it
isn't missed when Section 3's fix is eventually implemented.

**Not fixed this week**: same reasoning as Sections 2 and 3 — genuine
new infrastructure (a real caching layer, and separately, migrating the
rate limiter to Redis-backed storage) rather than a hardening fix to
existing behavior, and this specific pairing (worker scaling + shared
rate-limit storage) needs to be implemented and tested together, not
independently, to avoid exactly the silent regression described above.

## 5. Frontend Loading

**Method**: ran a real, current production build (`next build`) rather
than rely on bundle-size figures from earlier weeks' build logs, to get
an accurate, up-to-date picture.

✅ **Bundle sizes are genuinely small and consistent across the whole
app — no red flags found.** Every one of the 34 real routes has a First
Load JS between 88 kB and 109 kB, with the 87.3 kB shared baseline
common to all of them. No single page is a dramatic outlier heavier than
the rest, which is the usual symptom of an un-code-split heavy
dependency (e.g. a charting library or rich-text editor) leaking into
the shared bundle rather than being loaded only on the page that needs
it. `next.config.js` itself is minimal and unremarkable — no red flags,
nothing to correct.

**Not separately load-tested**: actual client-side runtime performance
(time-to-interactive under real network conditions, React render
performance on data-heavy pages like the orchestrator activity timeline
or the leads pipeline board with many real leads) was not measured this
week — bundle size is a reasonable proxy but not a substitute for real
runtime profiling, which is out of scope for this audit pass and would
be a reasonable pre-launch check rather than a Week 12 hardening task.

## Summary of Performance Review (Sections 1–5)

Two genuine, significant findings requiring real infrastructure work
before production (not silently downgraded to minor notes): **(1)** no
periodic/scheduled background execution exists anywhere (Section 2),
and **(2)** the combination of fully-synchronous AI calls with a
single-worker production server command is a real capacity risk that
should block production traffic until addressed (Section 3), which
itself has a direct, documented interaction with the rate limiter's
in-memory storage (Section 4) that must be fixed together, not
separately. Database query patterns are genuinely sound (Section 1,
with one honestly-scoped moderate finding), and frontend bundle size is
genuinely healthy (Section 5) with no action needed.

No code changes were needed to close any Performance finding this week
beyond the one docstring correction (Section 2) — every other item is a
real architectural gap requiring genuine new work, correctly deferred to
the Deployment section of the final report rather than rushed.

