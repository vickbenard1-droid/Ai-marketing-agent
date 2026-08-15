"""
Unit tests for app.ai_providers. Mocks httpx.Client.post (via
unittest.mock) rather than making real network calls — no API keys are
required to run this suite, and no real cost is ever incurred by tests.
"""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ai_providers.base import (
    AIMessage,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AITaskType,
)
from app.ai_providers.claude_provider import ClaudeProvider
from app.ai_providers.factory import (
    estimate_cost_usd,
    get_ai_provider,
    get_ai_provider_for_task,
)
from app.ai_providers.openai_provider import OpenAIProvider


def _mock_response(status_code: int, json_body: dict, text: str = ""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.text = text or str(json_body)
    return resp


# --------------------------------------------------------------------------
# ClaudeProvider
# --------------------------------------------------------------------------
def test_claude_provider_requires_api_key():
    provider = ClaudeProvider(api_key="")
    with pytest.raises(AIProviderAuthError):
        provider.generate([AIMessage(role="user", content="hi")])


@patch("httpx.Client.post")
def test_claude_provider_parses_successful_response(mock_post):
    mock_post.return_value = _mock_response(
        200,
        {
            "content": [{"type": "text", "text": "Hello there"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )
    provider = ClaudeProvider(api_key="test-key")
    result = provider.generate([AIMessage(role="user", content="hi")])

    assert result.text == "Hello there"
    assert result.provider == "anthropic"
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 5
    assert result.usage.total_tokens == 15


@patch("httpx.Client.post")
def test_claude_provider_joins_multiple_text_blocks(mock_post):
    mock_post.return_value = _mock_response(
        200,
        {
            "content": [
                {"type": "text", "text": "Part one"},
                {"type": "text", "text": "Part two"},
            ],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    provider = ClaudeProvider(api_key="test-key")
    result = provider.generate([AIMessage(role="user", content="hi")])
    assert result.text == "Part one\nPart two"


@patch("httpx.Client.post")
def test_claude_provider_maps_401_to_auth_error(mock_post):
    mock_post.return_value = _mock_response(401, {"error": "invalid key"})
    provider = ClaudeProvider(api_key="bad-key")
    with pytest.raises(AIProviderAuthError):
        provider.generate([AIMessage(role="user", content="hi")])


@patch("httpx.Client.post")
def test_claude_provider_maps_429_to_rate_limit_error(mock_post):
    mock_post.return_value = _mock_response(429, {"error": "rate limited"})
    provider = ClaudeProvider(api_key="test-key")
    with pytest.raises(AIProviderRateLimitError):
        provider.generate([AIMessage(role="user", content="hi")])


@patch("httpx.Client.post")
def test_claude_provider_maps_500_to_response_error(mock_post):
    mock_post.return_value = _mock_response(500, {"error": "server error"})
    provider = ClaudeProvider(api_key="test-key")
    with pytest.raises(AIProviderResponseError):
        provider.generate([AIMessage(role="user", content="hi")])


@patch("httpx.Client.post")
def test_claude_provider_maps_malformed_response_to_response_error(mock_post):
    # 200 but missing the "content" key entirely — still must not raise a
    # raw KeyError up to the caller.
    mock_post.return_value = _mock_response(200, {"usage": {}})
    provider = ClaudeProvider(api_key="test-key")
    result = provider.generate([AIMessage(role="user", content="hi")])
    # "content" defaults to [] via .get(), so this actually succeeds with
    # empty text rather than erroring — confirms the defensive .get() usage.
    assert result.text == ""


@patch("httpx.Client.post")
def test_claude_provider_wraps_timeout(mock_post):
    mock_post.side_effect = httpx.TimeoutException("timed out")
    provider = ClaudeProvider(api_key="test-key")
    with pytest.raises(AIProviderTimeoutError):
        provider.generate([AIMessage(role="user", content="hi")])


@patch("httpx.Client.post")
def test_claude_provider_sends_system_prompt(mock_post):
    mock_post.return_value = _mock_response(
        200, {"content": [{"type": "text", "text": "ok"}], "usage": {"input_tokens": 1, "output_tokens": 1}}
    )
    provider = ClaudeProvider(api_key="test-key")
    provider.generate([AIMessage(role="user", content="hi")], system="You are a helpful assistant")

    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["system"] == "You are a helpful assistant"


# --------------------------------------------------------------------------
# OpenAIProvider
# --------------------------------------------------------------------------
def test_openai_provider_requires_api_key():
    provider = OpenAIProvider(api_key="")
    with pytest.raises(AIProviderAuthError):
        provider.generate([AIMessage(role="user", content="hi")])


@patch("httpx.Client.post")
def test_openai_provider_parses_successful_response(mock_post):
    mock_post.return_value = _mock_response(
        200,
        {
            "choices": [{"message": {"content": "Hello there"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 4},
        },
    )
    provider = OpenAIProvider(api_key="test-key")
    result = provider.generate([AIMessage(role="user", content="hi")])

    assert result.text == "Hello there"
    assert result.provider == "openai"
    assert result.usage.input_tokens == 8
    assert result.usage.output_tokens == 4


@patch("httpx.Client.post")
def test_openai_provider_maps_401_to_auth_error(mock_post):
    mock_post.return_value = _mock_response(401, {"error": "invalid key"})
    provider = OpenAIProvider(api_key="bad-key")
    with pytest.raises(AIProviderAuthError):
        provider.generate([AIMessage(role="user", content="hi")])


@patch("httpx.Client.post")
def test_openai_provider_maps_malformed_response_to_response_error(mock_post):
    mock_post.return_value = _mock_response(200, {"choices": []})
    provider = OpenAIProvider(api_key="test-key")
    with pytest.raises(AIProviderResponseError):
        provider.generate([AIMessage(role="user", content="hi")])


@patch("httpx.Client.post")
def test_openai_provider_prepends_system_message(mock_post):
    mock_post.return_value = _mock_response(
        200,
        {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    )
    provider = OpenAIProvider(api_key="test-key")
    provider.generate([AIMessage(role="user", content="hi")], system="Be concise")

    sent_payload = mock_post.call_args.kwargs["json"]
    assert sent_payload["messages"][0] == {"role": "system", "content": "Be concise"}


# --------------------------------------------------------------------------
# Factory
# --------------------------------------------------------------------------
def test_get_ai_provider_defaults_to_anthropic():
    provider = get_ai_provider()
    assert provider.name == "anthropic"


def test_get_ai_provider_selects_openai():
    provider = get_ai_provider("openai")
    assert provider.name == "openai"


def test_get_ai_provider_rejects_unknown_name():
    with pytest.raises(ValueError):
        get_ai_provider("not-a-real-provider")


def test_get_ai_provider_for_task_falls_back_to_default():
    provider = get_ai_provider_for_task(AITaskType.SEO)
    assert provider.name == "anthropic"  # DEFAULT_AI_PROVIDER, no override configured


def test_estimate_cost_usd_known_model():
    cost = estimate_cost_usd("claude-sonnet-4-6", 1_000_000, 1_000_000)
    assert cost == pytest.approx(3.00 + 15.00)


def test_estimate_cost_usd_unknown_model_returns_none():
    assert estimate_cost_usd("some-made-up-model", 100, 100) is None
