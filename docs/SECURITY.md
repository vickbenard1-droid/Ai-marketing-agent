# Security Documentation

This is a reference for how this application handles security, and
what a deployer/operator needs to know. For the full investigative
record — what was checked, the real vulnerabilities found and fixed,
and the exact evidence behind each — see `docs/audit/SECURITY_AUDIT.md`
(639 lines covering all 13 areas of the Week 12 security audit).

## Authentication

JWT-based (`app/auth/dependencies.py`). Access and refresh tokens are
distinguished by an internal `type` claim — a refresh token cannot be
used as an access token. Missing and invalid tokens both produce an
identical 401 (no information leak about which failure occurred).

## Multi-tenant isolation

Every tenant-scoped endpoint requires a real `OrganizationMember` row
matching both the caller's identity and the `X-Organization-Id` header
— never a client-supplied organization ID taken on faith. This was
verified exhaustively across all 139 routes in the application during
the Week 12 audit.

**Two real cross-tenant vulnerabilities were found and fixed this
week** (both in the Meta Ads spend-limit endpoints — one read, one
mutation) where a resource was fetched by a path-supplied ID with no
check that it belonged to the caller's organization. Both are fixed,
covered by permanent regression tests
(`app/tests/integration/test_meta_ads_isolation_api.py`), and the fix
pattern (fetch, then verify `resource.organization_id ==
member.organization_id` before use) is now applied consistently. A
second, broader sweep confirmed no other instance of this pattern
exists anywhere else in the codebase.

## Secrets and credentials

- All OAuth tokens are encrypted at rest (Fernet — authenticated
  symmetric encryption) via `app/core/security.py`. The app fails to
  start if `CREDENTIALS_ENCRYPTION_KEY` is unset.
- No API response schema anywhere includes a plaintext credential
  field. No endpoint calls the decrypt function directly — decryption
  only happens in service-layer code making the actual outbound API
  call.
- OAuth's CSRF protection (`state` parameter) uses a cryptographically
  random, genuinely single-use value with a real expiry, verified with
  a dedicated single-use enforcement check (marked used before the
  token exchange happens, closing a possible race-condition replay
  window).

## AI security

- **Prompt injection**: traced every path where untrusted, user-
  supplied text reaches an LLM prompt. In every case, the AI's output
  can only ever populate a data field (a draft's text, a plan step's
  description) — never trigger a real action directly from its own
  output.
- **The most significant finding of the audit**: the AI orchestrator's
  pre-execution approval pause was, before this week's fix, controlled
  by a boolean the AI planner itself set on its own generated plan — a
  successful prompt injection against the planner could theoretically
  have skipped the human-approval pause for a sensitive action. Fixed
  with a code-owned, closed set of structurally sensitive agents
  (`advertising_agent`, `content_agent`, `optimization_agent`) checked
  before any agent runs, regardless of what the AI's plan claims.
  Verified with a real adversarial simulation — a mocked AI plan
  containing exactly what a successful injection would produce —
  confirming the run correctly pauses with zero real side effects.
- **Defense in depth, verified concretely**: even before this week's
  fix, every sensitive agent's own internal design independently
  refuses to take a real action on its own authority (the Advertising
  Agent only ever creates a pending approval request, never spends
  directly; the Optimization Agent's autonomous path is independently
  gated by a real spend guard). This was proven, not assumed — a real
  test deliberately makes two of the three defensive layers pass to
  confirm the third still blocks the action on its own.
- AI output is never executed as code anywhere in this codebase
  (verified: zero `eval`/`exec`/AI-output-in-raw-SQL patterns exist).

## Spending controls

Every real function capable of increasing Meta Ads spend routes through
exactly 2 functions, both with a spend guard check built in — not
duplicated (or potentially omitted) at each call site. The autonomous
execution path has two independent layers (the optimization agent's own
safety checks, and the same spend guard every other path uses), plus —
as of this week — a third, independent billing usage-limit check. All
three were verified to independently block an action, not just assumed
to.

## Rate limiting

A global default (100/minute per IP) applies to every route without an
explicit stricter limit. **A real gap was found and fixed this week**:
the middleware that makes this default actually apply was missing
entirely — meaning it silently did nothing for ~190 routes before the
fix. Verified behaviorally (real requests actually triggering or not
triggering a 429), both before and after the fix.

**Known limitation for production scaling**: the rate limiter's storage
is in-memory, meaning it's per-process. If the deployment scales to
multiple worker processes (see `docs/DEPLOYMENT.md`), the rate limiter
must move to Redis-backed storage in the same change, or the effective
limit silently weakens.

## What's NOT yet addressed (see `docs/audit/SECURITY_AUDIT.md` and the final production-readiness report for full detail)

- No error-tracking service is integrated (no Sentry or comparable)
- Effectively no application-wide logging exists beyond 2 real call
  sites
- No backup/restore strategy exists

These are genuine, real gaps — not glossed over — and are restated as
concrete requirements in `docs/DEPLOYMENT.md`.

## Reporting a vulnerability

This is application-level documentation, not a hosted product with a
disclosure program. If you find a security issue while reviewing or
extending this codebase, treat it with the same rigor this audit
applied: verify it with a real, targeted test before and after any fix,
and add permanent regression coverage.
