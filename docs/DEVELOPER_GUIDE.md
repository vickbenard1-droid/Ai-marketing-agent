# Developer Documentation

This is for someone extending this codebase — where things live, the
real conventions to follow, and how to add something new correctly.
For *why* specific decisions were made, see `docs/ARCHITECTURE.md`. For
the database schema, see `docs/DATABASE.md`. For the API surface, see
`docs/API.md`.

## Repository layout

```
backend/app/
  agents/          Real BaseAgent subclasses (Strategy, Research,
                   Content, Advertising, Analytics, Optimization,
                   Sales, Reporting, + pre-existing Audience/SEO/AdCopy)
  ai_chat/         The chat feature (Week 3)
  ai_providers/    The Claude provider client - the ONLY place any
                   real AI API call happens (see below)
  ai_usage/        generate_and_track() - the single required entry
                   point for every AI call, also where the real
                   AI-token billing limit is enforced (Week 12)
  ai_utils/        Shared helpers (e.g. extract_json_object)
  analytics/       Unified analytics (Week 8): rollups, ingestion,
                   attribution, website tracking
  audit/           write_audit_log() - the single required entry
                   point for the generic security/compliance trail
  auth/            JWT auth, permission dependencies
  billing/         Usage-limit enforcement (Week 12)
  campaigns/       Campaign CRUD + AI generation (Weeks 3-5)
  content/         Content generation, SEO, repurposing (Weeks 4-5)
  core/            Settings, security primitives, rate limiting
  dashboard/       The summary dashboard
  db/              Session management, seed scripts, Alembic env
  integrations/    (reserved)
  knowledge/       get_business_knowledge() - the shared "what does
                   this org's business look like" context builder
                   every AI feature draws from
  leads/           Lead pipeline, qualification, follow-up, sales
                   agent (Week 10)
  mail/            Real email sending (Week 1)
  meta_ads/        Meta Ads integration: OAuth, spend guard, sync,
                   execution (Week 7)
  models/          Every SQLAlchemy model - see app/models/__init__.py
                   for import order (matters for FK dependencies)
  oauth/           The generic OAuth flow (state, callback handling)
  onboarding/       Onboarding wizard
  optimization/    The autonomous optimization agent (Week 9)
  orchestrator/    The multi-agent orchestrator (Week 11)
  organizations/   Org/member management
  projects/        Projects (a business's own sub-brands/products)
  prompts/         The PROMPT_REGISTRY - every real system prompt,
                   versioned
  publishing/      Scheduled post publishing + Celery tasks
  scheduling/      Scheduling recommendations
  storage/         (reserved)
  tasks/           Celery app configuration
  tests/           pytest suite (app/tests/integration,
                   app/tests/unit) + the e2e simulation script

frontend/
  app/(auth)/      Login, register, password reset - public routes
  app/(dashboard)/ Every authenticated page - one folder per feature
  components/      Shared UI (layout, ui primitives, feature-specific)
  lib/api.ts       The ONLY place fetch() calls to the backend happen
```

## Core conventions (read before writing code)

These aren't stylistic preferences — following them is how this
codebase stayed correct across 12 weeks of continuous extension, and
deviating from them is where several real bugs found during the Week
12 audit came from.

1. **Multi-tenancy is enforced at the API boundary, never assumed.**
   Every tenant-scoped endpoint depends on `get_current_org_member` or
   `require_permission(...)`, and every resource fetched by a
   path-supplied ID must be checked against the caller's real
   `organization_id` before use — `db.get(Model, id)` alone is never
   enough. See `docs/SECURITY.md` for the two real bugs this exact
   omission caused and how the fix pattern looks.

2. **AI narrates, never computes.** Any feature that shows the person
   a number (a total, a rate, a trend) must compute that number with
   real code — the AI's role, if any, is to describe or interpret
   numbers that were already computed, never to produce the number
   itself.

3. **Honest gaps over fabricated data.** A metric that can't be
   computed (no data yet, a platform that doesn't report it) renders as
   `None`/a dash, never a plausible-looking zero. Don't "helpfully"
   fill in a number that isn't real.

4. **Every real AI call goes through `generate_and_track()`**
   (`app/ai_usage/service.py`) — never call a provider's `.generate()`
   directly. This is what makes AI usage monitoring and the AI-token
   billing limit work automatically for every new agent; bypassing it
   silently breaks both.

5. **A sensitive action is a request, then a separate execute/approve.**
   Any code path that spends money, changes an ad account, publishes
   content, or takes an autonomous action must create a `PENDING`
   record with zero real side effects first — a human (or a
   separately-gated autonomous policy) must take a second, explicit
   step to actually execute it. See `docs/SECURITY.md`'s "AI security"
   section for the real vulnerability this discipline prevents when
   it's followed correctly, and the one place it wasn't (found and
   fixed in Week 12).

6. **Fail closed, never open**, for anything touching money, spend
   limits, or usage limits — an ambiguous or missing configuration
   should block the action, not default to permitting it.

## Adding a new AI agent

1. Subclass `BaseAgent` in `app/agents/` (see any existing agent for
   the shape).
2. Register it in `app/agents/__init__.py`'s `agent_registry`.
3. If it needs its own AI call (most wrap an existing service function
   instead — check first), add an `AITaskType`/`AIUsageSource` pair and
   route through `generate_and_track()`.
4. If it can take a real external action, mark it in
   `app.orchestrator.service._STRUCTURALLY_SENSITIVE_AGENTS` — this is
   a code-owned safety list the AI planner cannot override, regardless
   of what its own generated plan claims.

## Adding a new migration

Hand-author it against the real compiled model DDL (see any recent
migration in `alembic/versions/` for the pattern) rather than trust
`alembic revision --autogenerate` blindly. Verify with a real offline
`--sql` dry-run in **both** directions before committing — this has
caught real ordering and constraint bugs in every week this project has
added tables.

## Running things locally

See `docs/INSTALLATION.md`.

## Testing conventions

See `docs/audit/TESTING_SUMMARY.md` for what's covered, and
`app/tests/conftest.py` for the real fixtures (`client`, `db_session`,
`seeded_roles`, `seeded_plans`) every integration test builds on. A new
endpoint that creates a billing-gated resource (a campaign, content, a
connected account, an automated action) needs `seeded_plans` in its
test signature or it will hit a real, deliberate fail-closed error.
