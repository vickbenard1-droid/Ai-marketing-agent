"""
Content Agent.

Wraps Week 4's real generate_content() - creates a real Content row.
Note this is content GENERATION, not publishing: a generated Content
row starts in an unpublished/draft state (Week 6's scheduling/
publishing_service governs actually posting it), so this agent never
touches "publishing permissions" on its own - see
app.publishing.service for the separate, human-gated publish step.
"""
import uuid

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.content.generation_service import ContentGenerationError, generate_content
from app.models.content import ContentType


class ContentAgent(BaseAgent):
    name = "content_agent"
    description = "Generates real marketing content (social posts, blog posts, product descriptions, etc.) as an unpublished draft."

    def run(self, context: AgentContext, *, content_type: str | None = None, source_text: str | None = None, **kwargs) -> AgentResult:
        if not content_type:
            return AgentResult(success=False, output=None, notes="No content_type provided - the Content Agent needs to know what kind of content to generate.")
        try:
            resolved_type = ContentType(content_type)
        except ValueError:
            return AgentResult(success=False, output=None, notes=f"'{content_type}' is not a valid content type.")

        try:
            content = generate_content(context.db, organization_id=context.organization_id, actor_user_id=context.actor_user_id, content_type=resolved_type, source_text=source_text)
        except ContentGenerationError as exc:
            return AgentResult(success=False, output=None, notes=str(exc))

        return AgentResult(success=True, output={"content_id": str(content.id), "content_type": content.content_type.value, "body_preview": (content.body or "")[:200]}, requires_human_approval=False, notes="Content generated as an unpublished draft - a separate, human-gated step is required to actually publish it.")
