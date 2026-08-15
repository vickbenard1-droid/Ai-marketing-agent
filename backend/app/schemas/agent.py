from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    name: str
    description: str


class RunAgentRequest(BaseModel):
    brief: str | None = Field(
        default=None,
        max_length=4000,
        description="Optional free-form brief. Required by ad_copy_agent and seo_agent; "
        "optional (a sensible default is used) for marketing_strategy_agent and "
        "audience_research_agent.",
    )


class RunAgentResponse(BaseModel):
    agent: str
    success: bool
    output: str | None
    requires_human_approval: bool
    notes: str | None
