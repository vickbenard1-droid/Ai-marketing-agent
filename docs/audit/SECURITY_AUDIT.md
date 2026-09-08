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

## 4. Database Security

✅ **Sound — no raw SQL string interpolation anywhere.** Grepped the
entire codebase for f-string SQL (`f"SELECT`, `.execute(f"`, etc.) and
for any raw `.execute()` call outside Alembic migrations (which
legitimately use `op.execute()` for DDL): zero hits either way. Every
database interaction goes through the SQLAlchemy ORM/query-builder
layer, which parameterizes automatically — SQL injection risk is
structurally very low, not just "no injection found on inspection."

## 5. File Uploads

✅ **Reviewed in full — one real, genuine vulnerability found and fixed.**

`app/storage/client.py` is well-designed: object keys are namespaced by
organization (`organizations/{org_id}/content-assets/{uuid}.{ext}`), so
tenant isolation exists at the storage-key level too, not just the
database; the file-extension sanitizer explicitly defends against a
malformed filename (e.g. `photo.jpg?x=1`) producing a key with injected
characters. `app/api/v1/endpoints/content_assets.py` has a real,
sensible chunked-read cap independent of the per-type limits enforced
one layer down, so an oversized request body is rejected before its
bytes are even fully read into memory.

### 🔧 FOUND AND FIXED: content-type spoofing — uploads were validated against the client-supplied header, not the file's real content

`upload_asset` (`app/content/asset_service.py`) validated and stored
files using the `Content-Type` value from the multipart upload request —
a value the client fully controls and the browser does not verify
against the actual file bytes. An attacker could label a malicious
payload (e.g. HTML containing `<script>`) as `image/jpeg`, pass the
allow-list check, have it stored, and have it served back later via a
presigned URL carrying that same spoofed `Content-Type` — a real
stored-XSS-via-upload pattern if any client ever renders the response
instead of force-downloading it.

**Fix**: added `_sniff_content_type()` — real magic-byte detection for
all 7 allowed types (JPEG/PNG/GIF/WebP/MP4/QuickTime/WebM), hand-rolled
rather than a new dependency since the allow-list is small and fixed and
each signature is well-known and short. `upload_asset` now validates and
stores based on the *real sniffed type*, never the client's claim — the
claimed type is only echoed back in the rejection message shown to a
legitimate caller who genuinely mislabeled a file.

**Verified thoroughly**: confirmed all 7 real magic-byte signatures are
correctly detected in isolation; confirmed the actual exploit payload
(malicious HTML labeled `image/jpeg`) sniffs to `None` and is rejected
by the full `upload_asset` function with nothing stored; confirmed a
genuine file with an honestly-mismatched claimed type (real PNG bytes,
claimed as JPEG) still uploads correctly using its real type, so the fix
doesn't over-correct into rejecting legitimate uploads.

**Fixed 3 existing tests that broke as a direct, correct consequence**:
they uploaded placeholder bytes (`b"fakejpeg"`) that were never real
images — previously passed only because the vulnerable code trusted the
claimed type. Replaced the placeholder bytes with real JPEG magic bytes
(matching the pattern one already-correct test in the same file already
used) rather than weaken the new check to accommodate fake test data.
Left the legitimate negative test (`application/pdf`, expecting
rejection) untouched.

**Added a permanent regression test**
(`test_upload_asset_rejects_spoofed_content_type`) using the exact
malicious-HTML-labeled-as-image scenario, which also asserts
`put_object` was never called — confirming the payload never reaches
storage at all, not just that the HTTP response looks like a rejection.

191/191 backend tests pass (190 + 1 new).

## 6. Webhooks

**No public-facing HTTP webhook endpoint exists in this codebase.** The
Week 10 `GenericWebhookCRMAdapter` (`app/analytics/crm_adapter.py`)
processes webhook-*shaped* payloads (its own docstring explains this
design: no OAuth/secret-verification layer exists for generic
third-party CRMs), but confirmed by direct grep that nothing in
`app/api/v1/endpoints/` wires it to a real route — it's an internal
adapter, not a live attack surface. Recorded here as an accurate "does
not apply as built" rather than silently skipped, since the spec asked
for it explicitly.

The genuinely comparable real surface — public, unauthenticated,
receives external input — is Week 8's `/api/v1/track/*` endpoints,
reviewed here instead as the closest real equivalent.

### 🔧 FOUND AND FIXED: unbounded conversion value on the public tracking endpoint

`POST /track/conversion` is deliberately public and unauthenticated (the
tracking key is meant to live in a business's own public page source —
this is correct by design, not a bug). But `conversion_value_cents` had
no validation bound at all — `Optional[int] = None`, no `ge`/`le`. A
leaked or guessed tracking key (a realistic threat given it's
intentionally public) could be used to submit an arbitrarily large or
negative fake conversion value. This isn't a cross-tenant leak (it can
only write into the one organization whose key was used), but it's a
genuine data-integrity risk: `WebsiteTrackingEvent.conversion_value_cents`
feeds directly into `SalesAnalytics.revenue_cents`/ROAS (Week 10) — a
malicious or even just a badly-behaved script hitting this endpoint
repeatedly could corrupt the exact numbers the org's own sales agent and
optimization agent (Week 9) reason over and act on.

**Fix**: added `ge=0` (a conversion cannot have negative value) and
`le=10_000_000_00` ($10M — generous enough to never reject a real sale,
tight enough to block absurd/abuse-shaped input) to
`TrackConversionRequest.conversion_value_cents`.

**Verified**: a legitimate $150 sale still validates correctly; a
negative value and an absurd (~$1 trillion) value are both correctly
rejected; a conversion with no value at all (e.g. a newsletter signup —
a real, valid non-monetary conversion type) remains correctly allowed.

**Added permanent regression coverage** —
`app/tests/integration/test_tracking_api.py` (5 tests). This is also the
first permanent test file for the `/track/*` endpoints at all.
196/196 backend tests pass (191 + 5 new).

**Rate limiting on this endpoint** was already reviewed as sound in an
earlier pass — `120/minute` via the existing slowapi limiter — kept, not
re-litigated here; a determined attacker could still submit ~172,800
fake events/day within that limit, which the value-bound fix above
mitigates the worst consequence of, but this is worth carrying into the
Rate Limiting section as a residual, lower-severity consideration
(volume of fake page-views/small-value conversions, not unbounded
financial-figure corruption, which is now closed).
