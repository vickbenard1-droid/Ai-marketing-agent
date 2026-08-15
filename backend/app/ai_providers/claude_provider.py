"""
Claude (Anthropic) provider implementation.

Uses the Anthropic Messages API directly over httpx to avoid pinning an SDK
version this early. Can be swapped for the official `anthropic` SDK later
without changing the AIProvider interface.
"""
import httpx

from app.ai_providers.base import (
    AICompletionResult,
    AIMessage,
    AIProvider,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    ImageContentBlock,
    TokenUsage,
)
from app.core.config import settings

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"


def _to_anthropic_content(content):
    """
    Translates AIMessage.content (str, or a list of str/ImageContentBlock)
    into Anthropic's content-block wire format. A plain string passes
    through unchanged — the Messages API accepts a bare string for
    text-only messages, so this only needs to build the block-array form
    when an image is actually present.
    """
    if isinstance(content, str):
        return content
    blocks = []
    for item in content:
        if isinstance(item, str):
            blocks.append({"type": "text", "text": item})
        elif isinstance(item, ImageContentBlock):
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": item.media_type,
                        "data": item.data_base64,
                    },
                }
            )
    return blocks


class ClaudeProvider(AIProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        transport: object | None = None,
    ):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model
        # transport is None in production (real network). Tests inject an
        # httpx.MockTransport here instead of patching httpx.Client.post
        # globally — patching the class method would also intercept
        # FastAPI's TestClient, which is itself built on httpx.Client (see
        # app/tests/integration/test_agents_api.py for the incident this
        # fixed).
        self._transport = transport

    def generate(
        self,
        messages: list[AIMessage],
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AICompletionResult:
        if not self.api_key:
            raise AIProviderAuthError("ANTHROPIC_API_KEY is not configured")

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": m.role, "content": _to_anthropic_content(m.content)} for m in messages
            ],
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            with httpx.Client(timeout=60.0, transport=self._transport) as client:
                response = client.post(ANTHROPIC_API_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(f"Anthropic request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise AIProviderResponseError(f"Anthropic request failed: {exc}") from exc

        if response.status_code == 401:
            raise AIProviderAuthError("Anthropic rejected the API key")
        if response.status_code == 429:
            raise AIProviderRateLimitError("Anthropic rate limit exceeded")
        if response.status_code >= 400:
            raise AIProviderResponseError(
                f"Anthropic returned {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
            text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise AIProviderResponseError(f"Unexpected Anthropic response shape: {exc}") from exc

        return AICompletionResult(
            text="\n".join(text_blocks),
            provider=self.name,
            model=self.model,
            usage=usage,
            raw=data,
        )
