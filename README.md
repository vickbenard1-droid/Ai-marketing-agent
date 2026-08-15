# AI Marketing Agent

An AI marketing employee platform: campaign creation, SEO/social content
generation, scheduling, performance monitoring, and (in later weeks)
autonomous optimization with human approval workflows.

This document covers **Week 1 (foundation) + Week 2 (onboarding & org
management)**. See `docs/ARCHITECTURE.md` for technical rationale and
`docs/TESTING.md` for how to run tests.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL, SQLAlchemy 2.0, Alembic |
| Caching / background jobs | Redis, Celery |
| Email | SMTP (real sending; logs instead of sending if unconfigured) |
| AI providers | Claude (Anthropic) API, OpenAI API |
| Storage | S3-compatible object storage |
| Deployment | Docker, GitHub Actions, Vercel (frontend), Railway/Render/AWS (backend) |

## Folder structure

```
ai-marketing-agent/
├── backend/
│   ├── app/
│   │   ├── core/              # config, security, rate limiting, shared utils
│   │   ├── db/                 # SQLAlchemy base, session, role seeding
│   │   ├── models/              # ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── auth/                # auth business logic + FastAPI dependencies
│   │   ├── mail/                 # SMTP service, email templates, Celery task (Week 2)
│   │   ├── onboarding/           # business onboarding service (Week 2)
│   │   ├── organizations/        # team member management service (Week 2)
│   │   ├── audit/               # audit log writer
│   │   ├── ai_providers/       # Claude/OpenAI provider abstraction
│   │   ├── agents/              # BaseAgent + registry (no agents implemented yet)
│   │   ├── integrations/        # IntegrationProvider interface (no integrations yet)
│   │   ├── tasks/                # Celery app
│   │   ├── api/v1/              # FastAPI routers/endpoints
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   └── integration/
│   │   └── main.py
│   ├── alembic/                  # DB migrations (2: initial schema, Week 2 additions)
│   ├── requirements.txt
│   ├── Dockerfile                # production image
│   ├── Dockerfile.dev             # local dev image (hot reload)
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── (auth)/               # login, register, forgot/reset password
│   │   ├── (dashboard)/          # authenticated app shell — dashboard, profile,
│   │   │                          # business-profile, team
│   │   ├── onboarding/           # 10-step onboarding wizard (own layout, no sidebar)
│   │   ├── verify-email/         # standalone, works logged in or out
│   │   └── globals.css
│   ├── components/
│   │   ├── layout/               # Sidebar, Header, OrgSwitcher, UserMenu
│   │   └── ui/                    # Button, Field, FieldDark, TextareaField, ChipMultiSelect
│   ├── lib/                       # api.ts (typed API client), session.tsx
│   ├── Dockerfile
│   ├── Dockerfile.dev
│   └── .env.example
├── docs/
│   ├── ARCHITECTURE.md
│   └── TESTING.md
├── .github/workflows/ci.yml
├── docker-compose.yml
└── .gitignore
```

## Database schema

**Week 1:**
- **users** — global identity; can belong to multiple organizations.
- **roles** — 6 system-defined roles (Week 2, see below), permission flags.
- **organizations** — the tenant boundary.
- **organization_members** — join table, per-org role.
- **projects** — one client/brand/website per project.
- **connected_accounts** — generic table for any external platform connection.
- **audit_logs** — who did what, when, in which org.

**Week 2 additions** (migration `92763f7fa341`):
- **users**: added `avatar_url`, `phone`, `timezone`.
- **roles**: added `can_manage_campaigns`, `can_manage_content`, `can_view_analytics`;
  reseeded from 4 roles (owner/admin/**member**/viewer) to 6
  (owner/admin/**manager/analyst/content_manager**/viewer) — the migration
  safely reassigns any existing `member` memberships to `manager` before
  dropping the role, never orphaning a row.
- **email_tokens** — single-use, hashed tokens backing both email
  verification and password reset.
- **business_profiles** — one-to-one with `organizations`, holds the
  10-step onboarding questionnaire.
- **revoked_tokens** — `jti` denylist backing logout (refresh tokens only;
  access tokens are short-lived and stateless by design).

## User roles & permissions

| Role | Billing | Members | Projects | Integrations | AI actions | Campaigns | Content | Analytics |
|---|---|---|---|---|---|---|---|---|
| Owner | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Admin | No | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Manager | No | No | Yes | No | Yes | Yes | Yes | Yes |
| Content Manager | No | No | No | No | Yes | No | Yes | Yes |
| Analyst | No | No | No | No | No | No | No | View only |
| Viewer | No | No | No | No | No | No | No | View only |

Enforced server-side via `require_permission("<flag>")` on every mutating
endpoint — never trust the frontend to hide a button. An organization can
never be left with zero owners: the API blocks demoting or removing the
last owner.

## Setup instructions

### Option A — Docker Compose (recommended)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env: set SECRET_KEY and CREDENTIALS_ENCRYPTION_KEY (see
# generation commands inside the file). Leave SMTP_HOST empty for local
# dev — verification/reset emails are logged instead of sent, and the
# links inside them still work against your local frontend.

docker compose up --build
```

Then, in a second terminal:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.db.seed_roles
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:3000
- Postgres: localhost:5432 · Redis: localhost:6379

To see a verification or password-reset link during local dev, watch the
backend container logs — with `SMTP_HOST` unset, the full email (including
the link) is logged instead of sent.

### Option B — Running services locally without Docker

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"                                  # SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # CREDENTIALS_ENCRYPTION_KEY

alembic upgrade head
python -m app.db.seed_roles

uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

**Celery worker** (needed for real email delivery — without it, emails
still work via the eager-fallback log path in dev, but production sending
requires a running worker):

```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
```

## Authentication & onboarding flow

1. **Register** — account created, personal organization auto-created
   (caller becomes Owner), verification email sent (logged if SMTP isn't
   configured), redirected to `/onboarding`.
2. **Onboarding** — 10 steps: business name, website, industry, country,
   products/services, target customers, marketing goal, monthly budget,
   social platforms, advertising platforms. Each step saves immediately;
   refreshing mid-flow resumes at the last completed step.
3. **Dashboard** — shows real onboarding data (goal, budget, connected
   platform count) plus honest empty states for campaigns/content/leads/
   sales/spend, since none of that exists until a later week.
4. **Login** — goes straight to dashboard; a banner prompts to finish
   onboarding if incomplete.
5. **Forgot/reset password**, **verify/resend email**, **logout** (revokes
   the refresh token server-side) are all available from `/login` and the
   user menu.

## Testing

```bash
cd backend
pytest                          # 81 tests: unit + integration, SQLite in-memory
pytest --cov=app

cd frontend
npm run type-check
npm run lint
npm run build
```

See `docs/TESTING.md` for full coverage details, including how RBAC
enforcement and the owner-guard rules are tested.

## What's intentionally NOT built yet

- **Any of the 11 marketing agents**, **any platform integration**,
  **campaign/content/analytics functionality** — unchanged from Week 1.
- **Invite-by-email for people without an account.** Week 2's "add team
  member" only works for existing users; a real invite-token/accept flow
  is a later addition.
- **Refresh token revocation is a denylist, not a full session table.**
  Works correctly but doesn't yet support "see all your active sessions."
- **No SSR session / Next.js middleware route protection.** Auth state is
  resolved client-side from a JWT in localStorage; route guards are
  client-side `useEffect` redirects, not edge middleware.
- **Business name editing lives on the Organization, not a separate
  "company settings" page** — see `docs/ARCHITECTURE.md`.
- **Billing / plan enforcement**, **email delivery in CI** (SMTP isn't
  exercised in the test suite — the mail service's log-fallback path is
  what's tested; see `docs/TESTING.md`).

## Git commit recommendations

```
# Week 1 (see prior commits) ...

feat(backend): add SMTP mail service with log-fallback and email templates
feat(backend): add EmailToken, BusinessProfile, RevokedToken models
fix(backend): make db session pool kwargs conditional on Postgres dialect
feat(backend): expand Role permissions and reseed 6 Week 2 roles
feat(backend): add Week 2 migration (profile fields, roles, new tables)
feat(backend): add logout, password reset, and email verification flows
fix(backend): handle naive vs aware datetimes in token expiry checks
feat(backend): add user profile endpoints
feat(backend): add onboarding service and 10-step endpoints
feat(backend): add team member management with RBAC and owner guards
feat(backend): add dashboard summary endpoint with empty states
test(backend): add unit and integration tests for all Week 2 endpoints
feat(frontend): extend API client and session store for Week 2
feat(frontend): add forgot/reset password and verify-email pages
feat(frontend): add 10-step onboarding wizard
feat(frontend): add profile, business-profile, and team pages
feat(frontend): rewrite dashboard with real data and empty states
docs: update README, architecture, and testing docs through Week 2
```
