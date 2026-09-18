# Database Documentation

PostgreSQL 16 (SQLite in-memory for the test suite only — see
`app/tests/conftest.py`). As of Week 12, **50 real tables**, verified
directly against `Base.metadata` rather than counted by hand.

For the *why* behind specific design decisions (why `BusinessProfile`
is its own table, why roles were expanded additively with a guarded
migration, why logout uses a real revoked-token table instead of the
originally-speculated Redis denylist, and more), see
`docs/ARCHITECTURE.md` — this document is the *what*: the real schema
organized by subsystem.

## Migrations

Alembic. Every migration in this repository was hand-authored against
the real compiled model DDL and verified with a real offline `--sql`
dry-run in both the upgrade and downgrade direction before being
merged — not generated and trusted blindly. Run `alembic upgrade head`
to apply all migrations; see `docs/DEPLOYMENT.md`.

## Tables by subsystem

**Identity & organizations** (Week 1–2)
`users`, `organizations`, `organization_members`, `roles`,
`revoked_tokens`, `email_tokens`, `business_profiles`

**Projects & connected accounts** (Week 1, 6)
`projects`, `connected_accounts`, `oauth_states`

**Campaigns & content** (Week 3–6)
`campaigns`, `campaign_strategies`, `ad_copy_variants`,
`creative_concepts`, `experiments`, `content_items`, `content_assets`,
`content_repurpose_batches`, `seo_content`, `scheduled_posts`,
`publishing_logs`

**Chat & AI usage tracking** (Week 3)
`conversations`, `chat_messages`, `ai_usage_logs`

**Meta Ads** (Week 7)
`meta_ad_accounts`, `ad_account_spend_limits`, `meta_campaigns`,
`meta_campaign_spend_limits`, `meta_ad_sets`, `meta_ads`,
`meta_insight_snapshots`, `approval_requests`

**Unified analytics** (Week 8)
`metric_snapshots`, `conversion_types`, `conversion_events`,
`website_tracking_keys`, `website_tracking_events`

**Autonomous optimization** (Week 9)
`campaign_autonomy_settings`, `campaign_whitelists`,
`optimization_decisions`, `automated_action_logs`

**Leads & sales** (Week 10)
`leads`, `lead_stage_transitions`, `lead_qualification_settings`,
`lead_follow_ups`

**Multi-agent orchestrator** (Week 11)
`orchestration_runs`, `agent_activity_logs`, `agent_decisions`

**Billing** (Week 12)
`subscription_plans` (organizations link to this via
`organizations.subscription_plan_id` — the pre-existing
`organizations.plan_type` string column is a Week 1 placeholder,
confirmed genuinely unused anywhere in the codebase, kept rather than
removed this late in the project rather than risk an unrelated
migration)

**Cross-cutting**
`audit_logs` (a generic "who did what" security/compliance trail,
distinct from the AI-specific `agent_activity_logs` — see
`docs/audit/SECURITY_AUDIT.md` for why both exist)

## Multi-tenancy

Every tenant-scoped table has a real `organization_id` foreign key.
Isolation is enforced at the application layer (every query filters by
the authenticated caller's real organization membership — see
`docs/SECURITY.md`), not by Postgres row-level security. This was
exhaustively verified during the Week 12 security audit, including
finding and fixing 2 real cases where a resource was fetched without
that filter.

## Real-time computed data, never stored redundantly

Following the "AI narrates, never computes" and honest-gap-reporting
principles used throughout this codebase, several tables that might
look like they need a "totals" or "summary" column deliberately don't
have one — e.g. `ai_usage_logs`, `metric_snapshots`, and
`automated_action_logs` are always summed live at query time
(`app/billing/service.py::get_current_usage`,
`app/analytics/service.py::rollup_totals`) rather than maintaining a
separately-updated counter that could drift from the real underlying
rows.
