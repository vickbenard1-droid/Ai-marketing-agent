"""
Importing this package registers every concrete agent into
app.agents.base.agent_registry — so `import app.agents` (done once, in
app/api/v1/endpoints/agents.py) is enough for registry.get("...") to find
all of them, without every call site needing to import each agent module
individually.
"""
from app.agents.base import agent_registry
from app.agents.marketing_strategy import MarketingStrategyAgent
from app.agents.audience_research import AudienceResearchAgent
from app.agents.ad_copy import AdCopyAgent
from app.agents.seo import SEOAgent

agent_registry.register(MarketingStrategyAgent())
agent_registry.register(AudienceResearchAgent())
agent_registry.register(AdCopyAgent())
agent_registry.register(SEOAgent())
