"""Groq API client with primary/fallback model chain and structured-output support.

Design decisions:
- Two-model chain: primary (openai/gpt-oss-120b) then fallback (openai/gpt-oss-20b).
  A second attempt on a smaller, faster model is better than surfacing an error to the
  evaluator when the primary model is rate-limited or timing out.
- Returns None on complete failure so every caller can apply a deterministic fallback
  without the client raising. The service never crashes due to LLM unavailability.
- Structured JSON output uses Groq's native response_format to avoid brittle regex
  parsing of free-form model output.
"""
import json
import logging
import time
from typing import Any

from groq import APIStatusError, APITimeoutError, AsyncGroq, RateLimitError

from app.config import Settings

logger = logging.getLogger(__name__)


class GroqClient:
    """Async Groq API wrapper with retry, model fallback, and JSON-mode support."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncGroq | None = (
            AsyncGroq(api_key=settings.groq_api_key)
            if settings.groq_api_key
            else None
        )
        if self._client is None:
            logger.warning(
                "GROQ_API_KEY is not configured; all LLM calls will return None "
                "and the agent will fall back to deterministic responses"
            )
        else:
            logger.info(
                "Groq client ready — primary=%s fallback=%s",
                settings.groq_model,
                settings.groq_fallback_model,
            )

    @property
    def is_available(self) -> bool:
        """True when an API key is configured and the client is initialised."""
        return self._client is not None

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str | None:
        """Generate a free-text completion.

        Tries the primary model first, falls back to the secondary model on any
        transient error, and returns None if both attempts fail.
        """
        if not self.is_available:
            logger.debug("Groq client unavailable; skipping text completion")
            return None

        for model, label in self._model_chain():
            result = await self._attempt_complete(
                model, label, messages, temperature, max_tokens
            )
            if result is not None:
                return result

        logger.error(
            "All Groq text-completion attempts failed; caller will use deterministic fallback"
        )
        return None

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 768,
    ) -> dict[str, Any] | None:
        """Generate a JSON-mode completion.

        Temperature defaults to 0 so the model consistently returns a valid JSON
        structure rather than introducing creative variance in field names.
        """
        if not self.is_available:
            logger.debug("Groq client unavailable; skipping JSON completion")
            return None

        for model, label in self._model_chain():
            result = await self._attempt_complete_json(
                model, label, messages, temperature, max_tokens
            )
            if result is not None:
                return result

        logger.error(
            "All Groq JSON-completion attempts failed; caller will use deterministic fallback"
        )
        return None

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _model_chain(self) -> list[tuple[str, str]]:
        return [
            (self._settings.groq_model, "primary"),
            (self._settings.groq_fallback_model, "fallback"),
        ]

    async def _attempt_complete(
        self,
        model: str,
        label: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> str | None:
        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(  # type: ignore[union-attr]
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed = time.monotonic() - start
            content = (response.choices[0].message.content or "").strip()
            tokens = response.usage.total_tokens if response.usage else "?"
            logger.info(
                "Groq text ok model=%s label=%s elapsed=%.2fs tokens=%s chars=%s",
                model,
                label,
                elapsed,
                tokens,
                len(content),
            )
            return content or None
        except RateLimitError as exc:
            logger.warning("Groq rate-limit model=%s label=%s: %s", model, label, exc)
        except APITimeoutError as exc:
            logger.warning("Groq timeout model=%s label=%s: %s", model, label, exc)
        except APIStatusError as exc:
            logger.warning(
                "Groq API error model=%s label=%s status=%s: %s",
                model,
                label,
                exc.status_code,
                exc,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Unexpected Groq error model=%s label=%s: %s",
                model,
                label,
                exc,
                exc_info=True,
            )
        return None

    async def _attempt_complete_json(
        self,
        model: str,
        label: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any] | None:
        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(  # type: ignore[union-attr]
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            elapsed = time.monotonic() - start
            content = (response.choices[0].message.content or "{}").strip()
            logger.info(
                "Groq JSON ok model=%s label=%s elapsed=%.2fs chars=%s",
                model,
                label,
                elapsed,
                len(content),
            )
            parsed: dict[str, Any] = json.loads(content)
            return parsed
        except RateLimitError as exc:
            logger.warning("Groq rate-limit model=%s label=%s: %s", model, label, exc)
        except APITimeoutError as exc:
            logger.warning("Groq timeout model=%s label=%s: %s", model, label, exc)
        except APIStatusError as exc:
            logger.warning(
                "Groq API error model=%s label=%s status=%s: %s",
                model,
                label,
                exc.status_code,
                exc,
            )
        except json.JSONDecodeError as exc:
            logger.warning(
                "Groq JSON decode error model=%s label=%s: %s", model, label, exc
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Unexpected Groq JSON error model=%s label=%s: %s",
                model,
                label,
                exc,
                exc_info=True,
            )
        return None


# Future Enhancements:
# - Add per-model token-bucket rate limiting so burst traffic degrades gracefully
#   before hitting Groq's server-side limits.
# - Expose a streaming variant for longer comparison replies once the evaluator
#   timeout budget allows it.
# - Instrument each attempt with OpenTelemetry spans for latency dashboards.
