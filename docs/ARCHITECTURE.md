# Architecture

## Why these decisions were made

### Multi-tenancy: Organization as the tenant boundary

`User` and `Organization` are many-to-many via `OrganizationMember`, which
carries a per-membership `role_id`. This is what makes every user structure
in the product vision work with one schema:

- **Individual user** — a personal `Organization` is auto-created at
  registration (`app/auth/service.py::register_user`), owned by that user.
- **Business with a team** — invite other users into the same
  `Organization` with different roles (invite flow not built this week, but
  the schema supports it today).
- **Agency with multiple clients** — an `Organization` with `is_agency=True`
  can have many `Project`s, one per client.

Tenant isolation is enforced at the API boundary, not just the database: the
`get_current_org_member` dependency requires an `X-Organization-Id` header
and checks the caller has an `OrganizationMember` row for it, rather than
trusting an `organization_id` the client puts in a request body. Every
tenant-scoped endpoint should depend on this (or `require_permission`,
which wraps it) rather than reimplementing the check.

### Role as a table, not an enum

`Role` is a normal table with boolean permission flags
(`can_manage_billing`, `can_manage_members`, etc.), seeded with four system
roles (`owner`, `admin`, `member`, `viewer`) via `app/db/seed_roles.py`.
This was chosen over a Python enum specifically so agencies can define
custom roles later (e.g. "Client Viewer — sees reports only") without a
schema migration — only a new `Role` row.

### ConnectedAccount: one generic table for every platform

Rather than a `MetaAdsAccount`, `GoogleAdsAccount`, `ShopifyAccount`, etc.
table per integration, there's one `ConnectedAccount` table with a
`platform` enum column. Adding TikTok support later means adding
`"tiktok_ads"` to `PlatformType` — not a new table, not a new migration
pattern, not new joins in every query that touches connected accounts.
Credentials are stored as a single `encrypted_credentials` text column
(Fernet-encrypted via `app.core.security.encrypt_secret`), since OAuth
token shapes vary by provider and forcing them into typed columns would
undo the benefit of the generic table.

The tradeoff: this table can't enforce platform-specific required fields at
the database level. That validation belongs in each platform's future
`IntegrationProvider` implementation, not the schema.

### AI provider abstraction

`app/ai_providers/base.py` defines `AIProvider` (one method: `generate()`).
`ClaudeProvider` and `OpenAIProvider` both implement it via direct HTTP
calls (not the official SDKs, to avoid pinning SDK versions this early —
easy to swap in later without touching the interface). `get_ai_provider()`
in `factory.py` is the only place that knows which provider is "default."

This exists now, ahead of any agent implementation, because every future
agent (Ad Copy, SEO, Campaign Optimization, ...) should depend on
`AIProvider`, never import `httpx` and call Anthropic/OpenAI directly. That
discipline is what lets a customer choose their provider, or lets Anthropic
add a third provider later, without touching agent logic.

### Agents and integrations: interfaces only, by design

`app/agents/base.py` (`BaseAgent`, `AgentContext`, `AgentResult`,
`AgentRegistry`) and `app/integrations/base.py` (`IntegrationProvider`) are
scaffolding with zero concrete implementations. This is intentional — Week
1 scope explicitly excludes agent and integration implementation. The
interfaces exist now so:

1. The API layer's future shape (`registry.get("ad_copy_agent").run(...)`)
   is already decided, avoiding a per-agent-endpoint sprawl.
2. `AgentResult.requires_human_approval` is part of the type from day one,
   because "human approval workflows" is a named product requirement — it
   shouldn't be bolted on after agents already exist without it.

### Audit logging: service function, not a decorator or middleware

`write_audit_log()` is called explicitly from endpoints/services that
perform sensitive mutations (see `organizations.py::create_organization`
for the pattern). It does **not** commit — the caller commits as part of
their existing transaction, so the audit row is atomic with the change it
describes. A global middleware approach was considered and rejected for
Week 1: it would log every request generically, but the audit log's value
is in recording *meaningful* actions with resource-specific context
(`resource_type`, `resource_id`, `metadata_json`), which is easier to get
right at the call site than to infer from a request/response pair.

### Security posture

- Passwords: argon2 via passlib (`app/core/security.py`).
- Tokens: JWT access (30 min default) + refresh (7 day default), each
  carrying a `jti` for future revocation-list support (not implemented yet
  — see README "not built" list).
- Secrets: centralized in `app/core/config.py::Settings`, loaded from `.env`
  via pydantic-settings. No module should call `os.environ` directly.
- Credential-at-rest encryption: Fernet, key from
  `CREDENTIALS_ENCRYPTION_KEY`, used for `ConnectedAccount.encrypted_credentials`.
- Rate limiting: slowapi, in-memory for local dev. `/auth/login` and
  `/auth/register` carry a dedicated `10/minute` limit on top of the
  app-wide default, since they're the highest-value targets for
  credential-stuffing and registration-spam bots.
- IDs: UUID primary keys everywhere (`UUIDPKMixin`), not sequential
  integers — avoids cross-tenant ID enumeration.

## What would change first if traffic/scale grew

These aren't Week 1 work, but are worth naming so later decisions don't
contradict this foundation:

- `app/db/session.py` uses a sync SQLAlchemy engine. It's structured so the
  async engine can be swapped in without touching model code, but every
  endpoint would need to move to `async def` + `AsyncSession` at that point.
- The in-memory rate limiter (`slowapi`) works for a single backend
  instance. Multi-instance deployment needs a Redis-backed limiter — the
  Redis connection already exists in the stack, so this is a config change,
  not new infrastructure.
- JWT revocation (logout-everywhere, forced re-auth) needs a `jti` denylist,
  most naturally stored in Redis with TTL matching token expiry.

---

# Week 2: Onboarding & Organization Management

## Logout / token revocation: DB table, not the Redis denylist Week 1 speculated

Week 1's architecture doc named a `jti` denylist in Redis as the future
approach. Week 2 implements it as a Postgres table (`RevokedToken`)
instead. Reasoning: revoked tokens need to persist for the lifetime of the
refresh token (7 days by default) regardless of Redis restarts/evictions,
and the write volume (one row per logout) is low enough that a DB table
with an indexed `jti` lookup is simpler to reason about and doesn't add a
Redis-availability dependency to the login/refresh path. Only refresh
tokens are checked against this table — access tokens stay fully stateless
(see `app/models/revoked_token.py`). Revisit for Redis if logout volume
ever makes the DB write path a bottleneck; the interface
(`is_refresh_token_revoked`) doesn't change either way.

## EmailToken: one table, two purposes

Email verification and password reset need identical mechanics — a
single-use, expiring, hashed token tied to a user — so they share one
`EmailToken` table with a `token_type` discriminator rather than two
near-identical tables. The token itself is never stored in plaintext (only
its SHA-256 hash), mirroring how passwords are handled: a database read
should never hand out a working link. See `app/models/email_token.py`.

## Why opaque tokens instead of JWTs for verification/reset

JWTs are stateless by design, which is exactly wrong for these two flows —
both need to be reliably single-use (checked via `used_at`), and a
stateless token can't enforce that without a parallel used-token table
anyway, at which point the JWT's statelessness bought nothing. A random
opaque token (`secrets.token_urlsafe(32)`) with a DB row is simpler and
gets single-use enforcement for free.

## BusinessProfile as its own table, not columns on Organization

`Organization` is read on nearly every authenticated request (via
`get_current_org_member`). Onboarding data is optional, evolving, and
read far less often — keeping it in a separate `BusinessProfile` table
means the tenant-critical `Organization` table's shape and query cost stay
unaffected as onboarding questions are added or changed in later weeks.
The one exception is business *name*, which stays on `Organization.name`
— it's not onboarding-specific data, it's the same name used everywhere
else in the app (org switcher, headers, audit logs), so onboarding step 1
edits it via the existing `PATCH /organizations/current` endpoint rather
than duplicating a `business_name` column on `BusinessProfile`.

## Role expansion: additive, with a guarded data migration

Week 1 shipped 4 roles (owner, admin, member, viewer). Week 2's spec calls
for 6 (owner, admin, manager, analyst, content_manager, viewer) — notably,
`member` isn't in the new set. Rather than repurpose `member`'s row (which
would silently change the permissions of anyone already holding it), the
migration adds the 3 new roles, reassigns any `OrganizationMember` pointing
at `member` to `manager`, and only then deletes the `member` row. See the
migration file's own docstring for how this was verified — offline
`--sql` mode can't exercise a data migration (no connection to read from),
so the reassignment logic was verified by direct execution against a
seeded session, not by the same offline dry-run used for the DDL.

Three new permission flags (`can_manage_campaigns`, `can_manage_content`,
`can_view_analytics`) were added to `Role` because the original 6 flags
couldn't distinguish Manager, Analyst, and Content Manager — all three
needed `can_execute_ai_actions=True` for meaningfully different reasons.

## Owner-guard invariant

`app/organizations/members_service.py` blocks two operations: demoting the
organization's only owner, and removing the organization's only owner.
Both are enforced with a live count query (`_owner_count`) at the moment
of the mutation, not a cached flag — an organization must always have at
least one member who can grant billing/member permissions, or it becomes
unrecoverable without direct database access.

## Team member "invite": existing users only, by design

`POST /organizations/current/members` requires the invitee to already have
an account. A real invite flow (send an email with a signup link, create
the membership on accept) is a meaningfully different feature — it needs
its own token type, its own email template, and a decision about what
happens if the invite is never accepted — and building a shortcut version
of it here would likely need to be redone rather than extended. The
current behavor fails clearly ("no account exists for that email") rather
than silently creating a shadow account.

## Dashboard summary: real queries only, explicit empty states

`GET /dashboard/summary` never fabricates a number. Fields backed by real
tables (business name, marketing goal, budget, connected platform count)
are queried live; fields with no backing table yet (campaigns, content,
leads, sales, spend) are hardcoded to `0`/`None` with a docstring
explaining why, so a future week's implementation is a query change, not a
"remove the placeholder" hunt. See `app/schemas/dashboard.py`.

