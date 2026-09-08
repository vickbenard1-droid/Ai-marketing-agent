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

**Not yet checked:** whether every *service-layer* function that takes an
`organization_id` parameter is actually called with the authenticated
caller's org id everywhere (vs. some endpoint accidentally trusting a
path/body param instead of `member.organization_id`) — this is a
resource-level check, one layer below what I've verified so far. Continuing
next.
