# AI Agent Documentation

Technical reference for the multi-agent system. For plain-language,
customer-facing coverage, see `docs/USER_GUIDE.md`. For the specific
security properties and the real vulnerability found and fixed in this
system, see `docs/SECURITY.md`.

## The 11 real registered agents

Pulled directly from the live `agent_registry`
(`app/agents/base.py`), not written from memory — this is the
real, current, complete list as of Week 12:

| Agent | What it does |
|---|---|
| `marketing_strategy_agent` | Analyzes the business and produces a marketing strategy: customer personas, goals, recommended channels, and a practical plan. |
| `audience_research_agent` | Defines target audience segments, their pain points, buying motivations, and how to target each one. |
| `ad_copy_agent` | Writes headlines, primary text, descriptions, CTAs, and variations for a campaign brief. |
| `seo_agent` | Suggests keywords, search intent, SEO titles, meta descriptions, content outlines, and hashtags. |
| `research_agent` | Researches market context using only real business knowledge on file — honestly does not fabricate competitor or market data this app has no live source for. |
| `content_agent` | Generates real marketing content as an unpublished draft — publishing is always a separate, human-gated step. |
| `advertising_agent` | Proposes Meta Ads campaign launches/budget changes as `PENDING` approval requests — **structurally never executes spend directly** (see below). |
| `analytics_agent` | Returns real, computed performance totals and derived metrics — no AI narration applied; this agent's output IS the data. |
| `optimization_agent` | Scans whitelisted Meta campaigns for real, data-triggered signals and generates decisions for human review. |
| `sales_agent` | Analyzes real lead-to-sale pipeline data, grounded only in real recorded leads and campaigns. |
| `reporting_agent` | Assembles a plain-language performance report from real, already-computed analytics and sales data. |

Note: `ad_copy_agent` and `content_agent` are both real and intentionally
kept distinct — ad copy variants for a specific campaign brief vs.
general social/blog/product content — rather than merged, per this
project's own "do not destroy existing functionality" rule when the
newer agent was added in Week 11.

## The orchestrator

`app/orchestrator/service.py`. Given a goal in plain language (e.g.
"help me get 100 sales"), it:

1. **Plans**: an AI call produces an ordered list of steps, each naming
   one agent from the list above and whether that step needs human
   approval.
2. **Validates the plan against the real registry** — an agent name
   the AI invents that doesn't actually exist is silently dropped, not
   trusted. A plan with zero valid steps fails the run outright rather
   than proceed with nothing real to do.
3. **Executes one step at a time**, writing a real
   `AgentActivityLog` row before and after each step — this is the
   Activity Timeline shown in the UI, and it records exactly what the
   step is doing, why, what data it used, what it recommends, and what
   was actually executed.
4. **Pauses before any structurally sensitive step, no exceptions.**
   `advertising_agent`, `content_agent`, and `optimization_agent` are a
   code-owned, closed set
   (`app.orchestrator.service._STRUCTURALLY_SENSITIVE_AGENTS`) checked
   *before* the agent is ever called — regardless of what the AI's own
   plan claims about whether that step needs approval. This is the fix
   for the most significant finding of the Week 12 security audit: the
   AI's own plan output used to be the only thing deciding whether to
   pause, which a sufficiently effective prompt injection could
   theoretically have exploited. The fix is verified with a real
   adversarial test — a mocked plan claiming a sensitive step needs no
   approval — confirming the pause still happens and the agent is never
   invoked. See `docs/SECURITY.md` for the full account.

## Memory

`app/orchestrator/memory.py`. Deliberately **not** a vector-similarity
RAG index — every category of "memory" this system draws on is small
enough per organization to query directly and completely:

- **Business knowledge** — `app.knowledge.service.get_business_knowledge`
  (products, audience, brand voice, recent activity)
- **Campaign performance** — real `MetricSnapshot` rollups
- **Customer information** — real `Lead` records
- **Previous decisions, successful & failed strategies** —
  `AgentDecision.outcome`, a real, durable record this system writes
  to every time an agent makes a decision
- **Brand voice** — folded into business knowledge

## Human control (the spec's explicit requirement)

Every agent that can take a real external action is structurally
prevented from doing so on its own authority:

- `advertising_agent` can only ever call a `request_*()` function,
  which creates a `PENDING` approval record with zero real API calls —
  actual execution requires a separate, explicit human action (or a
  separately-gated autonomous policy), still passing through the same
  spend guard every other path uses.
- `content_agent` can only ever create an unpublished draft `Content`
  row — publishing is a wholly separate, human-gated step.
- `optimization_agent`'s scan can only ever produce
  `OptimizationDecision` rows for human review, or — for a campaign an
  organization has explicitly opted into autonomous mode for — pass
  through Week 9's own independent safety checks (whitelist, autonomy
  level, daily action count, budget-increase limit, daily spend
  ceiling) plus the Week 12 billing usage limit, verified as three
  genuinely independent layers, not one relying on the others.

## AI usage tracking

Every real AI call in this entire system — every agent above, plus
chat, campaign generation, and content generation — passes through
exactly one function: `app.ai_usage.service.generate_and_track`.
Confirmed by direct search: no other code anywhere calls a provider's
`.generate()` method. This is also where the real AI-token billing
limit (Week 12) is enforced, automatically covering every agent without
needing to touch any of them individually.

## Adding a new agent

See `docs/DEVELOPER_GUIDE.md`'s "Adding a new AI agent" section.
