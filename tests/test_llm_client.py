"""Unit tests for GroqClient.

All Groq API calls are mocked — no real network access needed.
Tests verify retry behaviour, model fallback, JSON parsing, and the None-on-failure
contract that lets callers apply deterministic fallbacks.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.llm.client import GroqClient


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _make_settings(*, api_key: str = "test-key") -> Settings:
    return Settings(
        GROQ_API_KEY=api_key,
        GROQ_MODEL="llama-3.3-70b-versatile",
        GROQ_FALLBACK_MODEL="llama-3.1-8b-instant",
    )


def _make_text_response(content: str) -> MagicMock:
    usage = MagicMock()
    usage.total_tokens = 42
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_json_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    response.usage = None
    return response


# ------------------------------------------------------------------ #
# Initialisation                                                       #
# ------------------------------------------------------------------ #

def test_client_unavailable_when_no_api_key() -> None:
    settings = _make_settings(api_key="")
    client = GroqClient(settings)

    assert client.is_available is False


def test_client_available_when_api_key_set() -> None:
    with patch("app.llm.client.AsyncGroq"):
        settings = _make_settings()
        client = GroqClient(settings)

        assert client.is_available is True


# ------------------------------------------------------------------ #
# complete() — free text                                               #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_complete_returns_text_on_success() -> None:
    with patch("app.llm.client.AsyncGroq") as mock_groq_cls:
        mock_groq = AsyncMock()
        mock_groq_cls.return_value = mock_groq
        mock_groq.chat.completions.create = AsyncMock(
            return_value=_make_text_response("What role are you hiring for?")
        )

        client = GroqClient(_make_settings())
        result = await client.complete([{"role": "user", "content": "test"}])

        assert result == "What role are you hiring for?"
        assert mock_groq.chat.completions.create.call_count == 1


@pytest.mark.anyio
async def test_complete_returns_none_when_client_unavailable() -> None:
    settings = _make_settings(api_key="")
    client = GroqClient(settings)

    result = await client.complete([{"role": "user", "content": "test"}])

    assert result is None


@pytest.mark.anyio
async def test_complete_falls_back_to_secondary_model_on_rate_limit() -> None:
    from groq import RateLimitError

    with patch("app.llm.client.AsyncGroq") as mock_groq_cls:
        mock_groq = AsyncMock()
        mock_groq_cls.return_value = mock_groq

        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError(
                    message="rate limit",
                    response=MagicMock(status_code=429, headers={}),
                    body={},
                )
            return _make_text_response("fallback reply")

        mock_groq.chat.completions.create = side_effect

        client = GroqClient(_make_settings())
        result = await client.complete([{"role": "user", "content": "test"}])

        assert result == "fallback reply"
        assert call_count == 2


@pytest.mark.anyio
async def test_complete_returns_none_when_both_models_fail() -> None:
    from groq import APITimeoutError

    with patch("app.llm.client.AsyncGroq") as mock_groq_cls:
        mock_groq = AsyncMock()
        mock_groq_cls.return_value = mock_groq
        mock_groq.chat.completions.create = AsyncMock(
            side_effect=APITimeoutError(request=MagicMock())
        )

        client = GroqClient(_make_settings())
        result = await client.complete([{"role": "user", "content": "test"}])

        assert result is None
        assert mock_groq.chat.completions.create.call_count == 2


@pytest.mark.anyio
async def test_complete_returns_none_for_empty_content() -> None:
    with patch("app.llm.client.AsyncGroq") as mock_groq_cls:
        mock_groq = AsyncMock()
        mock_groq_cls.return_value = mock_groq
        mock_groq.chat.completions.create = AsyncMock(
            return_value=_make_text_response("   ")
        )

        client = GroqClient(_make_settings())
        result = await client.complete([{"role": "user", "content": "test"}])

        assert result is None


# ------------------------------------------------------------------ #
# complete_json() — JSON mode                                          #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_complete_json_parses_valid_response() -> None:
    payload = '{"selected_names": ["OPQ32r"], "reply": "Good fit."}'

    with patch("app.llm.client.AsyncGroq") as mock_groq_cls:
        mock_groq = AsyncMock()
        mock_groq_cls.return_value = mock_groq
        mock_groq.chat.completions.create = AsyncMock(
            return_value=_make_json_response(payload)
        )

        client = GroqClient(_make_settings())
        result = await client.complete_json([{"role": "user", "content": "test"}])

        assert result == {"selected_names": ["OPQ32r"], "reply": "Good fit."}


@pytest.mark.anyio
async def test_complete_json_returns_none_on_decode_error() -> None:
    with patch("app.llm.client.AsyncGroq") as mock_groq_cls:
        mock_groq = AsyncMock()
        mock_groq_cls.return_value = mock_groq
        mock_groq.chat.completions.create = AsyncMock(
            return_value=_make_json_response("not valid json {{{")
        )

        client = GroqClient(_make_settings())
        result = await client.complete_json([{"role": "user", "content": "test"}])

        assert result is None


@pytest.mark.anyio
async def test_complete_json_returns_none_when_client_unavailable() -> None:
    settings = _make_settings(api_key="")
    client = GroqClient(settings)

    result = await client.complete_json([{"role": "user", "content": "test"}])

    assert result is None


@pytest.mark.anyio
async def test_complete_json_sends_json_object_response_format() -> None:
    payload = '{"selected_names": [], "reply": "none"}'

    with patch("app.llm.client.AsyncGroq") as mock_groq_cls:
        mock_groq = AsyncMock()
        mock_groq_cls.return_value = mock_groq
        mock_groq.chat.completions.create = AsyncMock(
            return_value=_make_json_response(payload)
        )

        client = GroqClient(_make_settings())
        await client.complete_json([{"role": "user", "content": "test"}])

        call_kwargs = mock_groq.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}
