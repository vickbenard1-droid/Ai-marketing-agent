"""
Base agent interface.

Week 3 implements four concrete agents (Marketing Strategy, Audience
Research, Ad Copy, SEO — see app/agents/marketing_strategy.py etc.). Not
yet implemented: Creative Strategy, Social Media, Campaign Management,
Campaign Optimization, Analytics, Sales Conversion, Reporting (future
weeks).

Every agent subclasses BaseAgent, is called with an AgentContext, and
returns an AgentResult. The AgentRegistry is where they register so the
API layer can dispatch to "run agent X for org Y" generically instead of
hardcoding a per-agent endpoint for each one — see
app/api/v1/endpoints/agents.py.

AgentContext.project_id is optional: no Project CRUD API exists yet (see
docs/ARCHITECTURE.md), so every Week 3 agent operates at the organization
level via app.knowledge.service.get_business_knowledge(). The field is
kept so agent code doesn't need to change shape once Projects ship —
only get_business_knowledge()'s query would need to start filtering by
project.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session


@dataclass
class AgentContext:
    db: Session
    organization_id: uuid.UUID
    actor_user_id: Optional[uuid.UUID]
    project_id: Optional[uuid.UUID] = None


@dataclass
class AgentResult:
    success: bool
    output: Any
    requires_human_approval: bool = False
    notes: str | None = None


class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = ""

    @abstractmethod
    def run(self, context: AgentContext, **kwargs) -> AgentResult:
        """Execute the agent's task. Implemented by concrete agent subclasses."""
        raise NotImplementedError


class AgentRegistry:
    """
    Central registry agents register themselves into, e.g.:

        registry.register(AdCopyAgent())

    The API layer can then do registry.get("ad_copy_agent").run(context, ...)
    without a growing if/elif chain.
    """

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())


agent_registry = AgentRegistry()
