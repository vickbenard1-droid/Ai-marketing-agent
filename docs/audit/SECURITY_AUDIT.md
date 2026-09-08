# Week 12 Security Audit — Working Notes

Status legend: ✅ reviewed & sound · ⚠️ real gap found · 🔧 fixed this week · ❓ needs manual/human decision

This file is built incrementally while reviewing the codebase, not written
from memory at the end. Each section records what was actually checked and
what was found — including gaps that won't be fixed this week, which get
carried into the final production-readiness report rather than silently
dropped.

---

## 1. Authentication

✅ **JWT-based, sound.** `get_current_user` (`app/auth/dependencies.py`)
decodes a bearer token, checks `type == "access"` (rejects a refresh token
used as an access token), loads the real `User` row, and checks
`is_active`. `oauth2_scheme` has `auto_error=False` so a missing token is
turned into the same 401 as an invalid one rather than a different FastAPI
default-generated error shape.

Reviewed the 9 genuinely public auth-adjacent routes
(register/login/logout/refresh/forgot-password/reset-password/verify-email/
resend-verification, plus OAuth callback and page-view/conversion
tracking) — every one is intentionally public for a real reason (you can't
require a token to get a token; a third-party OAuth redirect and a public
tracking pixel can't carry our bearer token). None are silently missing
auth that should be there.

## 2. Authorization / Organization Isolation

✅ **Reviewed exhaustively — all 139 routes across all 26 endpoint files.**

Method: regex-scanned every `@router.get/post/put/patch/delete(...)`
decorator across `app/api/v1/endpoints/*.py` for whether the route function
depends on `get_current_org_member` or `require_permission`. First pass
matched 120/139 — cross-checked the total decorator count (139, confirmed
by two independent counting methods) to catch anything my first regex
silently skipped. The gap was `@router.get("")` / `@router.post("")`
(empty-string paths — the collection-root routes like `GET /leads`) which
my first pattern's `"([^"]+)"` couldn't match since it required a
non-empty path. Fixed the regex and checked all 19 explicitly by hand.

Result: every tenant-scoped route genuinely has the dependency. The one
route with no `X-Organization-Id` requirement, `GET /organizations` (list
my orgs), is correct as designed — it's authenticated via
`get_current_user`, and is safe specifically because it filters by
`OrganizationMember.user_id == current_user.id` (the caller's own
identity), never by a client-supplied org id, so it cannot leak another
tenant's organizations. This is the intended "which orgs can I even pick
from" endpoint, used before an org context exists.

**Core mechanism (`app/auth/dependencies.py::get_current_org_member`):**
requires a real `OrganizationMember` row matching both the caller's user id
*and* the `X-Organization-Id` header — never trusts an `organization_id`
supplied in a request body. This is the correct pattern: tenant isolation
enforced at the API boundary by checking real membership, not by trusting
client-asserted identifiers.

**Resource-level isolation check (below route-level):** systematically
scanned for `db.get(Model, id)` and `db.query(Model).filter(Model.id ==
...)`-style single-resource fetches inside endpoint functions, where the
route-level dependency proves the caller belongs to *some* org, but the
fetched resource's *own* org membership must be checked separately before
returning/mutating it.

### 🔧 FOUND AND FIXED: real cross-tenant data leak in `GET /meta-ads/ad-accounts/{ad_account_id}/spend-limit`

`get_spend_limit` (`app/api/v1/endpoints/meta_ads.py`) required the caller
to be an authenticated member of *some* organization, but never checked
that the `ad_account_id` in the URL path belonged to *that* organization
before returning its spend limit. Any authenticated user in any
organization could pass another organization's real `ad_account_id` (a
UUID, but one that could be learned via, e.g., a shared link, a support
ticket, log exposure, or brute-force enumeration) and read that
organization's real daily spend limit and emergency-stop status.

This was caught only because a *second*, differently-shaped systematic
scan (searching for foreign-key filters without an accompanying
`organization_id` check, rather than re-trusting the earlier route-level
"has a dependency" check) surfaced it — three structurally similar
`db.get()` calls in the same file were checked by hand first and found
genuinely safe (each immediately verifies `resource.organization_id ==
member.organization_id` before use), which made it easy to assume the
file was uniformly safe. It wasn't; this one function used a `db.query()`
fetch instead of `db.get()`, so the "check every `db.get()` call" grep
didn't even see it. **Lesson applied**: a single detection method,
however systematic, can still miss a differently-shaped instance of the
same bug class — this is why a second pass with a different search
pattern is worth doing rather than treating one clean sweep as
conclusive.

**Fix**: added the identical fetch-then-verify-ownership pattern already
used correctly elsewhere in the same file — `db.get(MetaAdAccount,
ad_account_id)`, then `404` unless `ad_account.organization_id ==
member.organization_id`, before running the original query.

**Verified with a real exploit simulation, not just a unit check**:
registered two genuinely separate organizations via real HTTP, org A set
a real, distinctive spend limit (999999 cents), and org B's user
attempted to read it using org A's real `ad_account_id` — confirmed
`404`, confirmed the real number never appears in the response. Also
confirmed org A can still read its own data correctly (no
over-correction into a broken feature).

**Added permanent regression coverage**: `app/tests/integration/
test_meta_ads_isolation_api.py` (3 tests) — this is also the *first*
permanent automated test file for the `meta_ads` endpoints at all;
Weeks 7–11 (meta_ads, analytics, leads, optimization, orchestrator) had
no permanent test files before this, only the manual verification done
during each week's build. Flagged in the Testing section below as a
real, separate gap to address more broadly this week.

**Scope of this specific bug**: limited to this one endpoint. The
`PUT`/`POST` mutating endpoints in the same file were independently
verified safe (both by manual review and by the new regression test
`test_org_cannot_set_another_orgs_spend_limit`).
