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

### 🔧 FOUND AND FIXED: a SECOND, higher-severity cross-tenant vulnerability in the same file — `POST /meta-ads/ad-accounts/{ad_account_id}/emergency-stop`

Found immediately after fixing the first, by deliberately re-applying the
"second, differently-shaped scan" method to the *entire codebase* rather
than treating the first fix as closing the matter — searched every
endpoint file for `db.query(Model).filter(...).first/all/one/count()`
calls lacking an `organization_id`/`user_id` filter. This surfaced 6 hits;
4 were reviewed and confirmed genuinely safe (global email lookup during
unauthenticated password/verification flows — correctly never reveals
account existence; global org-slug uniqueness check; global system-`Role`
lookup by name — roles are shared, not tenant-scoped). The remaining 2
were the already-fixed first bug's own query line (now safe, upstream
ownership check added) — but reading that whole function in full revealed
a **third, sibling function in the same file with the identical missing
check**, one call below the fixed one, which the mechanical scan itself
hadn't flagged as new (same query shape, so it just looked like "more of
the same known issue" rather than an independently exploitable second
bug).

`set_emergency_stop` fetched `AdAccountSpendLimit` by `ad_account_id`
alone with **no ownership check**, and unlike the read-only bug fixed
above, this endpoint *mutates* real state: any authenticated user with
`can_manage_integrations` on their own organization could POST another
organization's real `ad_account_id` and either **force-enable an
emergency stop** (halting a different tenant's real advertising spend
without their knowledge or consent) or, if it happened to already be
stopped, **force-disable it** (silently resuming spend against that
tenant's wishes). The mutation was also attributed to `member.user_id` —
the attacker's own identity — meaning even the audit trail on the
mutated row would misrepresent who acted on it. This is a materially
worse bug than the first: unauthorized read of a number vs. unauthorized
control over another business's real ad spend safety switch.

**Fix**: identical fetch-then-verify-ownership pattern, applied to this
function too.

**Verified with a real two-organization mutation exploit test**: victim
org sets a real, distinct spend limit; attacker org calls the
emergency-stop endpoint against the victim's real `ad_account_id` with
`stopped: true` — confirmed `404`, confirmed the victim's real
`is_emergency_stopped` state is genuinely untouched by the attack
afterward (not just "the response was blocked" — checked the actual
persisted state), and confirmed the victim can still use their own
endpoint correctly (no over-correction).

**Regression coverage added** to the same test file (now 4 tests total).

### Extended resource-level sweep — every endpoint file, both `db.get()` and `db.query().filter()` shapes

Re-ran the ownership-check scan across the *entire* `app/api/v1/endpoints/`
directory (not just `meta_ads.py`), and specifically widened the
`db.query().filter()` pattern to be multi-line-aware — the two real bugs
above were both single-line filters, and I did not want to assume a
regex shape that happened to catch those two would catch everything else
too.

- Every `db.get(Model, id)` call codebase-wide (`auth.py`, `dashboard.py`,
  `meta_ads.py` ×3 now — the 3rd being the ownership-check line my own
  fix added, `organizations.py` ×2): all confirmed safe, either by
  fetching with the caller's own `member.organization_id` directly, or by
  an immediate ownership check before use.
- Widened `db.query().filter()` scan surfaced 2 genuinely new candidates
  the narrower single-line regex missed: `leads.py`'s
  `get_lead_transitions` and `orchestrator.py`'s `get_run_activity`. Both
  reviewed in full and confirmed safe — each calls a `_get_..._or_404`
  helper immediately beforehand that performs a real ownership check
  (`lead_service.get_lead(organization_id=..., lead_id=...)` /
  `OrchestrationRun.organization_id == organization_id` respectively) and
  raises 404 before the unguarded query below it ever runs. Read the
  helper functions themselves rather than trust their names.
- Remaining hits (`auth.py` email lookup, `organizations.py` slug/role
  lookups, `members.py` role list) re-confirmed as legitimately
  non-tenant-scoped, same reasoning as before — `members.py`'s own
  docstring explicitly explains why org membership is still required
  even though `Role` itself isn't tenant data, which is worth noting as
  a genuinely well-reasoned existing comment, not just a lucky pass.

**Conclusion**: the 2 bugs found and fixed in `meta_ads.py` were real and
were the only 2 — this broader, differently-shaped sweep across every
other file did not surface a third. Resource-level tenant isolation is
now confirmed sound across the full API surface, not just spot-checked.

**Methodological note carried forward**: route-level auth-dependency
presence (`get_current_org_member`/`require_permission` on the route) is
necessary but not sufficient proof of resource-level tenant isolation —
it confirms a caller belongs to *some* organization, not that a specific
path-referenced resource belongs to that same organization. Both layers
were checked explicitly in this sweep rather than the first implying the
second.

## 3. OAuth and Secrets Handling

✅ **Reviewed in full — genuinely sound, with one real defense-in-depth
gap found and fixed.**

**Credential encryption** (`app/core/security.py`): Fernet (authenticated
symmetric encryption), fail-closed at startup if
`CREDENTIALS_ENCRYPTION_KEY` is unset, `decrypt_secret` returns `None` on
tamper/invalid-key rather than raising or returning garbage.

**No plaintext credential ever reaches an API response**: confirmed
`ConnectedAccountPublic` (`app/schemas/connected_account.py`) has no
token field at all — and its own docstring explicitly frames adding one
as a security bug, not a missing feature, which is exactly the kind of
guardrail comment worth having. Confirmed by direct grep that zero
endpoint files anywhere call `decrypt_credentials_for_publishing` or
`decrypt_secret` directly — decryption only happens deep in service-layer
code that makes the actual outbound API call, never on any path that
returns to the client.

**OAuth CSRF protection (`state` parameter)**: reviewed
`app.oauth.service._consume_state` in full. Generated with
`secrets.token_urlsafe(32)` (256 bits, cryptographically secure). Genuine
single-use enforcement — `used_at` is set *before* the token exchange
happens, so a race condition replaying the same state can't succeed.
Checks all 4 real failure modes (missing / already-used / expired /
platform mismatch) and deliberately returns one generic error message for
all of them rather than telling a would-be attacker which specific check
their forged request failed — a genuinely thoughtful detail, not
something I'd have flagged as missing if it were absent, but worth
noting as evidence of real security-mindedness in the original build.

### 🔧 FOUND AND FIXED: `DEBUG` setting defaulted to the unsafe value, and wasn't even wired up

`app/core/config.py` had `DEBUG: bool = True` as the default, and
`app/main.py` never actually passed it into `FastAPI(debug=...)` at all —
so this specific flag currently controls nothing. Two separate problems
worth separating:

1. **Not currently exploitable** — Starlette's own debug mode (which can
   expose full stack traces, including local variable values such as
   decrypted secrets or tokens, in error responses to any client) was
   never actually enabled by this setting, because nothing read it.
2. **A real latent risk regardless**: a setting that exists, looks
   security-relevant by name, defaults to the unsafe value, and is
   currently inert is exactly the shape of thing a future change could
   wire up (e.g. someone adding `debug=settings.DEBUG` to `FastAPI(...)`,
   a natural and easy edit) without anyone noticing the default was wrong
   — at which point it becomes live and unsafe by default in any
   deployment that forgets to override it.

**Fix**: changed the default to `False` (explicit opt-in to debug mode
required via `.env` for local dev), and — since a fix that only changes
an unused default doesn't actually close anything — genuinely wired it
into `FastAPI(debug=settings.DEBUG)` so it becomes a real, functioning
safety control rather than dead configuration that merely looks safe.

**Verified**: `settings.DEBUG` is `False` by default, and `app.debug`
(the live FastAPI instance) genuinely reflects it — checked both, not
just the settings default in isolation.

**CORS**: `BACKEND_CORS_ORIGINS` defaults to a specific localhost origin
(dev-appropriate), not a wildcard — safe as a default, but genuinely
requires explicit production configuration to the real frontend domain;
flagged for the "needs manual configuration" section of the final report
rather than left implicit.

190/190 backend tests pass after this fix (no change in count — a config
default and wiring correction, not new test coverage).
