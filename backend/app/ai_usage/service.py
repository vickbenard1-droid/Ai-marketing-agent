"""
AI usage tracking service.

record_usage() is the single place that writes an AIUsageLog row — every
agent and the chat service should call generate_and_track() (not
provider.generate() directly) so no call site can forget to log usage.
This mirrors the same "one required entry point" pattern as
app.audit.service.write_audit_log().
"""
import time
import uuid

from sqlalchemy.orm import Session

from app.ai_providers.base import AICompletionResult, AIMessage, AIProvider, AIProviderError
from app.ai_providers.factory import estimate_cost_usd
from app.models.ai_usage_log import AIUsageLog, AIUsageSource


def record_usage(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    source: AIUsageSource,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    succeeded: bool,
    prompt_name: str | None = None,
    prompt_version: str | None = None,
    error_message: str | None = None,
    latency_ms: int | None = None,
) -> AIUsageLog:
    log = AIUsageLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        source=source,
        provider=provider,
        model=model,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost_usd(model, input_tokens, output_tokens),
        succeeded=succeeded,
        error_message=error_message,
        latency_ms=latency_ms,
    )
    db.add(log)
    db.flush()
    return log


def generate_and_track(
    db: Session,
    provider: AIProvider,
    messages: list[AIMessage],
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    source: AIUsageSource,
    system: str | None = None,
    prompt_name: str | None = None,
    prompt_version: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> AICompletionResult:
    """
    Calls provider.generate() and unconditionally records the attempt —
    on success with real token counts, on failure with 0 tokens and the
    error message — then re-raises. Callers (agents, chat service) should
    let AIProviderError propagate to their own caller (the API layer),
    which is responsible for turning it into an HTTP error; this function
    only guarantees the attempt is logged either way, not that failures
    are hidden.

    Does NOT commit the session — same convention as write_audit_log():
    the caller commits as part of its own transaction, so the usage log
    row is atomic with whatever else that request does.
    """
    started = time.monotonic()
    try:
        result = provider.generate(
            messages, system=system, max_tokens=max_tokens, temperature=temperature
        )
    except AIProviderError as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        record_usage(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            source=source,
            provider=provider.name,
            model=getattr(provider, "model", "unknown"),
            input_tokens=0,
            output_tokens=0,
            succeeded=False,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            error_message=str(exc),
            latency_ms=latency_ms,
        )
        raise

    latency_ms = int((time.monotonic() - started) * 1000)
    record_usage(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        source=source,
        provider=result.provider,
        model=result.model,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        succeeded=True,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        latency_ms=latency_ms,
    )
    return result


def get_usage_summary(db: Session, organization_id: uuid.UUID) -> dict:
    """
    Aggregates all AIUsageLog rows for an organization into the shape
    app.schemas.ai_usage.AIUsageSummary expects. A raw dict (not the
    Pydantic model) is returned so this module doesn't need to import
    from app.schemas — services stay independent of the API layer's
    response shapes, matching the pattern elsewhere in this codebase.
    """
    from sqlalchemy import func

    from app.models.ai_usage_log import AIUsageLog as _AIUsageLog

    rows = db.query(_AIUsageLog).filter(_AIUsageLog.organization_id == organization_id).all()

    total_calls = len(rows)
    successful = [r for r in rows if r.succeeded]
    failed = [r for r in rows if not r.succeeded]

    costs = [r.estimated_cost_usd for r in rows if r.estimated_cost_usd is not None]

    by_source: dict[str, int] = {}
    for r in rows:
        key = r.source.value
        by_source[key] = by_source.get(key, 0) + 1

    return {
        "total_calls": total_calls,
        "successful_calls": len(successful),
        "failed_calls": len(failed),
        "total_input_tokens": sum(r.input_tokens for r in rows),
        "total_output_tokens": sum(r.output_tokens for r in rows),
        "total_estimated_cost_usd": sum(costs) if costs else None,
        "by_source": by_source,
    }
