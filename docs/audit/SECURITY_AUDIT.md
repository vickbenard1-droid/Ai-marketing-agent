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

## 7. Rate Limiting

✅ **Reviewed in full — one real, significant gap found and fixed.**

Explicit `@limiter.limit(...)` decorators exist only on `auth.py` (5
routes) and `tracking.py` (2 routes) — the genuinely public/
unauthenticated surfaces. This is defensible by itself, but
`app.core.rate_limit` also configures a *global default* limit
(`RATE_LIMIT_DEFAULT`, `100/minute` per IP) intended to cover every other
route, including the ~190 authenticated business endpoints with no
explicit decorator.

### 🔧 FOUND AND FIXED: the global default rate limit was never actually being enforced

`app/main.py` set `app.state.limiter` and registered the
`RateLimitExceeded` exception handler, but never added
`SlowAPIMiddleware`. Without that middleware, slowapi's `default_limits`
do nothing for any route lacking an explicit `@limiter.limit(...)`
decorator — meaning every authenticated business endpoint (AI content
generation, the orchestrator, Meta Ads sync triggers, all of Weeks 7–11)
had genuinely **no rate limiting at all**, despite the configuration
implying a 100/minute global default existed.

**Verified this behaviorally before fixing, not just from reading the
code**: set `RATE_LIMIT_DEFAULT=3/minute` and fired 6 rapid real requests
at a real, undecorated authenticated route (`GET /dashboard/summary`) —
all 6 returned `200`, zero `429`s, proving the default genuinely did
nothing.

**Fix**: added `app.add_middleware(SlowAPIMiddleware)` in `app/main.py`.
Re-ran the identical behavioral test post-fix: first 3 requests
succeeded, requests 4–6 correctly returned `429` — the exact expected
shape at a 3/minute limit.

**A real mistake in my own first regression test, caught and corrected**:
my first attempt used `importlib.reload()` on `app.main`,
`app.core.config`, and `app.core.rate_limit` to get a fresh
`RATE_LIMIT_DEFAULT` for the test. Running it alone passed — but running
the *full* suite afterward broke 12 unrelated tests across 3 other files
(`test_scheduled_posts_api.py`, `test_tracking_api.py`,
`test_users_api.py`), because reloading real application modules mid-
test-run corrupts shared state (a second `FastAPI` app object, stale
dependency overrides) that other test files' fixtures depend on. Caught
by running the full suite after adding the new test, not just the new
file in isolation — exactly the discipline this whole audit already
depends on, applied to my own new code this time. Rewrote the test to
build a fully isolated `FastAPI`/`Limiter` instance that never touches
real application modules, plus one focused test that imports the real
`app.main.app` read-only and asserts `SlowAPIMiddleware` is present in
its middleware stack (a genuine regression guard against this specific
fix ever being silently reverted) — 3 tests total, none of which mutate
shared state. Ran the full suite twice after the rewrite to rule out
ordering-sensitivity, not just once.

199/199 backend tests pass (196 + 3 new).

**Residual, lower-severity note carried over from Section 6**: the
100/minute global default (and the tracking endpoints' own 120/minute)
still permit meaningful sustained volume from a single IP. Reasonable
for now; a production deployment fielding real abuse would likely want
per-organization or per-API-key limits on top of the per-IP default,
which this app does not yet have. Flagged for the final report rather
than built this week, since the spec asks for a genuine present-vs-
absent audit, not new rate-limiting infrastructure beyond closing the
gap found.

## 8. Prompt Injection and AI Tool Abuse

**Method**: traced every path where untrusted, business-user-supplied
free text (lead notes, product interest, a goal statement typed into the
orchestrator) reaches an LLM prompt, and for each one asked the real
question — not "could the AI be manipulated into saying something odd"
(assume yes, always, for any LLM), but "if it were, could that ever
translate into a real, unauthorized action without a human in the
loop."

**Lead follow-up generation** (`app.leads.followup`): `lead.notes` is
genuinely untrusted, business-user-supplied text interpolated directly
into the `LEAD_FOLLOW_UP_SYSTEM` prompt. Confirmed safe by structure,
not by the prompt's own instructions: the AI's output can only ever
populate a `LeadFollowUp.subject`/`.body` text field. Sending still
requires a completely separate, explicit human-initiated
`send_follow_up()` call — even a successfully manipulated AI response is,
at worst, a bad draft a person sees and can reject before anything is
sent.

### 🔧 FOUND AND FIXED: the orchestrator's pre-execution approval pause was decided by the AI's own plan output

**This is the most significant finding of the whole audit and the one
most directly responsive to the spec's "AI must never be allowed to
bypass application permissions" requirement.**

`advance_run()` (`app.orchestrator.service`) decided whether to pause a
run for human approval *before running an agent* using only
`step["requires_approval"]` — a boolean the AI planner itself set on
each step of its own generated plan. The `ORCHESTRATOR_PLANNING_SYSTEM`
prompt instructs the AI to mark spending/advertising/publishing steps as
`requires_approval: true`, but that is a *prompt instruction*, not a
*code guarantee*. A sufficiently effective prompt injection — e.g. via
adversarial business-knowledge content or a goal statement crafted to
manipulate the planner — could plausibly cause the AI to emit
`{"agent_name": "advertising_agent", "requires_approval": false}`, and
the orchestrator would have trusted that and called the agent
immediately, with no pause at all.

**Verified this was genuinely exploitable as designed, then verified the
actual real-world severity before fixing** — read every structurally
sensitive agent's own `run()` method in full first, rather than assume
the worst. Found each one independently refuses to take a real external
action regardless of how it's invoked: `AdvertisingAgent` only ever
calls `request_*()` (creates a `PENDING` `ApprovalRequest`, zero Meta API
calls — Week 7's own separate execution gate + spend guard still stand
between this and any real spend), `ContentAgent` only ever creates an
unpublished draft `Content` row (Week 6's own separate, human-gated
publishing step still required), `OptimizationAgent` only ever calls
`scan_organization()`, itself gated by Week 9's independent
autonomy-settings/whitelist/spend-guard checks. **This meant the actual
exploitable consequence of the bug was narrower than it first appeared —
not unauthorized spend or publishing, but the orchestrator's own
pre-execution pause (a real, spec-required control in its own right)
being skippable** — genuine defense-in-depth already prevented the
worst-case outcome. This finding is still real and still fixed in full,
not downgraded to a non-issue, because (a) it's the exact mechanism the
spec's human-control requirement asks for at the orchestrator layer
specifically, and (b) a future agent added later without an equally
careful independent backstop would have had no protection at all if this
were left as the only gate.

**Fix**: introduced `_STRUCTURALLY_SENSITIVE_AGENTS`, a code-owned,
closed set (`advertising_agent`, `content_agent`, `optimization_agent`)
checked *before* `agent.run()` is ever called, regardless of what the
AI's plan claims. The plan's own `requires_approval` flag is preserved
as an *addition* — an AI plan can still mark an otherwise-safe step as
needing approval — but can never loosen the structural requirement for
a sensitive agent.

**Verified with a real adversarial simulation**, not just a unit
assertion: constructed a mocked AI plan response containing exactly what
a successful prompt injection against the planner would try to produce
— `advertising_agent` with `requires_approval: false` and an
action_description reading "Launch immediately, ignore review" — ran it
through the real `create_run`/`advance_run` pipeline, and confirmed the
run correctly paused (`PAUSED_FOR_APPROVAL`) with **zero**
`ApprovalRequest` rows created, meaning the agent was never invoked at
all. Repeated for `content_agent` and `optimization_agent`. Also
confirmed no over-correction: a genuinely non-sensitive agent
(`analytics_agent`) with the same `requires_approval: false` still
auto-executes normally, and a plan that explicitly *adds* approval to a
non-sensitive agent is still honored.

**Added permanent regression coverage** —
`app/tests/integration/test_orchestrator_service.py` (5 tests,
also the first permanent test file for the orchestrator at all).
204/204 backend tests pass (199 + 5 new).

**Not yet reviewed**: unauthorized tool execution beyond the orchestrator
(e.g. whether any other AI-facing surface can cause a real side effect
from within its own output) and spending controls specifically —
continuing next.

## 9. Spending Controls (dedicated review)

**Method**: found every real call site of the only two functions in the
entire codebase capable of increasing real Meta Ads spend
(`execute_budget_change`, `execute_campaign_status_change` in
`app.meta_ads.execution_service`) by exhaustive grep, then verified each
site's protection — rather than re-verify the spend guard's own logic
again (already covered in the original Week 7/9 builds and referenced
throughout this audit).

**Exactly 3 real call sites exist**: the direct `POST
/meta-ads/approval-requests/{id}/execute` API endpoint, Week 9's
`process_decision`'s manual/assisted paths, and Week 9's autonomous
path. **The spend guard check lives inside the two execution functions
themselves**, not duplicated (or, worse, omitted) at each call site —
meaning every caller structurally inherits the protection and there is
no way to reach real spend-changing behavior that bypasses it without
editing those two functions directly.

**Verified the autonomous path's defense-in-depth concretely, not just
architecturally**: the autonomous execution path has TWO independent
checks in sequence — Week 9's own `safety.assert_can_execute_autonomously`
(whitelist, autonomy level, daily action count, budget-increase percent,
Week-9-configured daily spend) runs first, then the *same* Week 7 spend
guard every other execution path uses runs again inside
`execute_budget_change` itself. Constructed a real test that deliberately
configures Week 9's own checks to be maximally permissive (generous
limits, correctly whitelisted, AUTONOMOUS mode) while leaving Week 7's
`AdAccountSpendLimit` entirely unconfigured — confirmed the system still
correctly blocks the autonomous execution via the second, independent
layer, with the `OptimizationDecision` status correctly landing on
`EXECUTION_FAILED` (never silently `EXECUTED`) and the campaign's real
budget genuinely unchanged afterward. This is real evidence of two
independently-failing-closed layers, not one relying on the other to
catch what it misses.

**AI output is never executed as code**: searched the entire codebase for
`eval(`, `exec(`, AI-generated text interpolated into a raw SQL query, or
any comparable code-injection pattern — zero matches. Every AI response
in this app is consistently treated as data: parsed via
`extract_json_object` and validated field-by-field against closed
enums/the real agent registry (see Section 8), never as instructions to
run.

## Summary of Sections 1–9 (Security Audit)

10 real, exploitable-or-genuinely-latent issues found and fixed across
the review, from a real cross-tenant data leak down to a config default
that wasn't yet wired to anything:

1. Cross-tenant read leak — Meta Ads spend limit (Section 2)
2. Cross-tenant mutation — Meta Ads emergency stop (Section 2)
3. Content-type spoofing in file uploads (earlier session, verified this
   session — see commit `6331817`)
4. `DEBUG` defaulted unsafe and was unwired (Section 3)
5. Unbounded conversion value on the public tracking endpoint (Section 6)
6. Global default rate limit never actually enforced — missing
   `SlowAPIMiddleware` (Section 7)
7. Orchestrator approval pause controllable by the AI's own plan output
   (Section 8) — the most significant finding

Every fix was verified with a real, targeted exploit or behavioral test
(not just a unit assertion of the fix's own logic), and every one has
permanent regression coverage. Backend test count grew from 186 (start
of Week 12) to 204, entirely through real security regression tests —
no feature work.

**Not yet reviewed**: database security and file uploads were reviewed
in an earlier session (see commit `6331817` for the file-upload finding)
but do not yet have their own dedicated write-up section in this
document — will backfill before the final report so the document is a
complete, accurate record of everything actually checked, not just what
was checked in this continuous session.

**Still to review under the original Week 12 security checklist**: none
remaining from the spec's explicit list — all 13 items (Authentication,
Authorization, Organization isolation, API security, OAuth, Secrets,
Database security, File uploads, Webhooks, Rate limiting, Prompt
injection, AI tool abuse, Spending controls) have now been covered at
least once. Moving to Testing, Performance, Monitoring, Billing,
Deployment, UX, the end-to-end simulation, and Documentation next.
