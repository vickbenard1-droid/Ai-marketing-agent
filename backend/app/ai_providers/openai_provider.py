"""
OpenAI provider implementation. Mirrors ClaudeProvider's shape exactly so
callers can swap providers without any conditional logic.
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

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o"


def _to_openai_content(content):
    """Translates AIMessage.content into OpenAI's chat content format —
    a bare string for text-only messages, or a list of {"type": "text"|
    "image_url", ...} parts when an image is present. OpenAI takes images
    as a data: URI rather than Anthropic's separate media_type + base64
    fields, so this isn't shared logic with the Claude provider."""
    if isinstance(content, str):
        return content
    parts = []
    for item in content:
        if isinstance(item, str):
            parts.append({"type": "text", "text": item})
        elif isinstance(item, ImageContentBlock):
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{item.media_type};base64,{item.data_base64}"},
                }
            )
    return parts


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        transport: object | None = None,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
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
            raise AIProviderAuthError("OPENAI_API_KEY is not configured")

        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(
            {"role": m.role, "content": _to_openai_content(m.content)} for m in messages
        )

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=60.0, transport=self._transport) as client:
                response = client.post(OPENAI_API_URL, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise AIProviderTimeoutError(f"OpenAI request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise AIProviderResponseError(f"OpenAI request failed: {exc}") from exc

        if response.status_code == 401:
            raise AIProviderAuthError("OpenAI rejected the API key")
        if response.status_code == 429:
            raise AIProviderRateLimitError("OpenAI rate limit exceeded")
        if response.status_code >= 400:
            raise AIProviderResponseError(
                f"OpenAI returned {response.status_code}: {response.text[:500]}"
            )

        try:
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            usage_data = data.get("usage", {})
            usage = TokenUsage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
            )
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise AIProviderResponseError(f"Unexpected OpenAI response shape: {exc}") from exc

        return AICompletionResult(
            text=text,
            provider=self.name,
            model=self.model,
            usage=usage,
            raw=data,
        )
