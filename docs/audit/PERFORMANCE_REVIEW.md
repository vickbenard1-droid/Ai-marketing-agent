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
