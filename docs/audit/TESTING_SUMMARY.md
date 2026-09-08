# Week 12 Testing — API Coverage Summary

## Method

Started from an automated gap analysis (endpoint file → expected test
file name), which flagged 11 files as having zero coverage. That
analysis was too coarse — this codebase groups some tests by *feature
concept* rather than by which router file defines the route (e.g.
`experiments` and `campaign_generation` tests live inside
`test_campaigns_api.py`; `content_generation` tests live inside
`test_content_api.py`; the one untested `connected_accounts` route lives
inside `test_oauth_api.py`). Three genuine false positives were caught
and corrected over the course of the week — two before writing any
code (checked existing files directly before assuming a gap), one after
writing tests and hitting a real failure that prompted investigation
rather than a quick patch.

A second, more precise sweep (matching each endpoint file's real
`APIRouter(prefix=...)` value against real test-file greps, rather than
filename convention) was run at the end to confirm the corrected
picture — and itself needed one manual correction for a parameterized
route prefix (`experiments`' `/campaigns/{campaign_id}/experiments` isn't
matched by a literal-string grep, since real test code uses an
f-string-interpolated ID). Verified that specific case by hand.

## Genuine gaps found and closed this week

| Endpoint file | Tests added | Notes |
|---|---|---|
| `leads.py` | 9 | Zero coverage before. Core Week 10 sales pipeline. |
| `optimization.py` | 6 | Zero coverage before. Core Week 9 autonomous agent. |
| `meta_ads.py` (workflow) | 7 | Complements pre-existing security-only isolation tests with the real request/approve/review business flow. |
| `orchestrator.py` (API) | 7 | Complements pre-existing security-only service-layer tests with the real HTTP surface. |
| `analytics.py` | 5 | Zero coverage before. Week 8 dashboard. |
| `connected_accounts.py` | 1 | Only `reauthorize` was genuinely untested; rest already covered in `test_oauth_api.py`. |
| `projects.py` | 6 | Zero coverage before — every other file's `POST /projects` calls were setup scaffolding, not dedicated coverage; GET/PATCH/DELETE were never exercised at all. |
| `business_profile.py` | 5 | Zero coverage before. |
| `campaign_generation.py` | 2 | Mostly a false positive — 5 tests already existed in `test_campaigns_api.py`. Added only the 2 genuinely missing cases (cross-org isolation, a role-permission case the existing tests couldn't distinguish). |
| Rate limiting (`app/main.py` wiring) | 3 | Found via the security audit, not the coverage sweep — a real infrastructure gap (see `SECURITY_AUDIT.md`). |
| Orchestrator human-control fix | 5 | Found via the security audit — the most significant finding of the audit (see `SECURITY_AUDIT.md`). |
| `tracking.py` | 5 | Found via the security audit (unbounded conversion value fix). |
| `meta_ads.py` (isolation) | 4 | Found via the security audit (the two cross-tenant vulnerabilities). |

**Total added this week: 65 tests** (186 → 252... plus 1 test-name fix
that didn't change the count, netting 66 real test functions added).
Every one was run individually first, then confirmed via a full-suite
run (not just the new file in isolation) before being committed — this
discipline specifically caught one real cross-test-pollution bug in an
early draft of the rate-limiting test (see `SECURITY_AUDIT.md` Section
7) before it reached `main`.

## Confirmed NOT gaps (false positives caught and corrected)

- `experiments.py` — covered in `test_campaigns_api.py`
- `connected_accounts.py` (mostly) — covered in `test_oauth_api.py`
- `content_generation.py` — covered in `test_content_api.py`
- `campaign_generation.py` (mostly) — covered in `test_campaigns_api.py`

## What this section does NOT cover (see other Week 12 sections/final report)

- **Unit tests** for individual service functions (scoring algorithms,
  spend-guard arithmetic, etc.) — these were extensively verified
  through direct execution during each week's original build (see the
  session history for Weeks 7–11), but that verification was
  interactive, not committed as permanent `pytest` unit tests. This is
  a real, distinct gap from API-level coverage and is not closed by the
  work recorded in this file.
- **Payment/billing tests** — no billing system exists yet (Week 12's
  Billing section is separate, not-yet-started work as of this
  writing).
- **Social publishing tests** — `test_scheduled_posts_api.py` exists and
  covers Week 6 scheduling; whether it exercises every real publishing
  platform path has not been separately audited as part of this file.
- **Advertising integration tests** beyond Meta Ads — Google Ads/GA4/
  Shopify/WooCommerce source clients (Week 8) have real, verified
  behavior from their original build but no permanent test file; not
  yet assessed here.
- **AI workflow tests** as an end-to-end category (a full orchestrator
  run from goal to completion across multiple real agents in sequence)
  — the orchestrator tests added this week cover individual steps and
  the approval-pause mechanism, not a full multi-step run.

These remain open items for the rest of Week 12's Testing phase and will
be addressed explicitly in the final production-readiness report rather
than silently left off it.
