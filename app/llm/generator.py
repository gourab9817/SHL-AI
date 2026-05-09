"""LLM-powered generation layer for shortlist selection, clarification, and comparison.

This module is the single point of contact between the LangGraph agent nodes and
the Groq API. It provides three public coroutines — one per agent behaviour that
benefits from natural-language generation — and falls back to deterministic
responses on any LLM failure so the agent is never blocked by API unavailability.

Design invariants:
- URLs are never passed to the LLM. Only product *names* are returned by the
  model, then resolved against the catalog. URL hallucination is structurally
  impossible.
- test_type is always derived from the resolved CatalogProduct.keys field, never
  from LLM output.
- The generator returns ([], "") for shortlist failures so callers fall through
  to the deterministic ShortlistPlanner — the agent always produces a response.
"""
import logging
from typing import Literal

from app.agent.responder import DeterministicResponder
from app.catalog import CatalogIndex, CatalogProduct
from app.conversation import ConversationContext
from app.llm.client import GroqClient
from app.llm.prompts import build_clarify_messages, build_compare_messages, build_shortlist_messages
from app.llm.types import ShortlistPlan
from app.retrieval.tokenizer import normalize_text

logger = logging.getLogger(__name__)


class LLMGenerator:
    """Orchestrates Groq LLM calls for shortlist selection, clarification, and comparison."""

    def __init__(
        self,
        client: GroqClient,
        catalog: CatalogIndex,
        responder: DeterministicResponder,
    ) -> None:
        self._client = client
        self._catalog = catalog
        self._responder = responder

    async def select_shortlist_with_reply(
        self,
        context: ConversationContext,
        candidates: list[CatalogProduct],
        intent: Literal["recommend", "refine"],
    ) -> tuple[list[CatalogProduct], str]:
        """Select a shortlist via the LLM and return it with a recruiter-friendly reply.

        Returns ([], "") when the LLM is unavailable or its output is unusable —
        the caller must then fall back to the deterministic ShortlistPlanner.
        """
        if not self._client.is_available:
            logger.debug("LLM unavailable; signalling caller to use deterministic planner")
            return [], ""

        messages = build_shortlist_messages(context, candidates, intent)
        raw = await self._client.complete_json(messages)

        if raw is None:
            logger.warning("LLM shortlist call returned None; signalling deterministic fallback")
            return [], ""

        plan = ShortlistPlan.from_llm_dict(raw)
        if not plan.is_valid:
            logger.warning(
                "LLM returned unusable shortlist plan (names=%d reply_len=%d); using deterministic fallback",
                len(plan.selected_names),
                len(plan.reply),
            )
            return [], ""

        resolved = self._resolve_names(plan.selected_names)
        if not resolved:
            logger.warning(
                "None of the %d LLM-selected names resolved to catalog products; using deterministic fallback",
                len(plan.selected_names),
            )
            return [], ""

        resolved = self._enforce_removals(resolved, context)

        logger.info(
            "LLM shortlist resolved intent=%s resolved=%d/%d names",
            intent,
            len(resolved),
            len(plan.selected_names),
        )
        return resolved, plan.reply

    async def generate_clarify_reply(self, context: ConversationContext) -> str:
        """Generate a focused one-sentence clarifying question.

        Falls back to DeterministicResponder.clarify() on any LLM failure.
        """
        if not self._client.is_available:
            return self._responder.clarify(context)

        messages = build_clarify_messages(context)
        reply = await self._client.complete(messages, temperature=0.3, max_tokens=128)

        if not reply:
            logger.debug("LLM clarify returned empty; using deterministic fallback")
            return self._responder.clarify(context)

        return reply.strip()

    async def generate_compare_reply(
        self,
        context: ConversationContext,
        products: tuple[CatalogProduct, ...],
    ) -> str:
        """Generate a grounded product-comparison reply.

        Falls back to DeterministicResponder.compare() on any LLM failure.
        """
        if not self._client.is_available or len(products) < 2:
            return self._responder.compare(products)

        messages = build_compare_messages(context, products)
        reply = await self._client.complete(messages, temperature=0.2, max_tokens=256)

        if not reply:
            logger.debug("LLM compare returned empty; using deterministic fallback")
            return self._responder.compare(products)

        return reply.strip()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _resolve_names(self, names: tuple[str, ...]) -> list[CatalogProduct]:
        """Map LLM-returned product names to catalog products, dropping misses."""
        resolved: list[CatalogProduct] = []
        seen: set[str] = set()
        for name in names:
            product = self._catalog.get_by_name(name)
            if product is None:
                logger.warning("LLM selected unknown product name %r — skipped", name)
                continue
            if product.entity_id in seen:
                continue
            seen.add(product.entity_id)
            resolved.append(product)
        return resolved

    def _enforce_removals(
        self,
        products: list[CatalogProduct],
        context: ConversationContext,
    ) -> list[CatalogProduct]:
        """Remove products explicitly requested for removal even if the LLM kept them."""
        removals = context.actions.requested_removals
        if not removals:
            return products

        normalized_removals = tuple(normalize_text(r) for r in removals if normalize_text(r))
        if not normalized_removals:
            return products

        kept: list[CatalogProduct] = []
        for product in products:
            normalized_name = normalize_text(product.name)
            should_remove = any(
                removal in normalized_name or normalized_name in removal
                for removal in normalized_removals
            )
            if should_remove:
                logger.info(
                    "Safety net removed LLM-kept product %r (matched removal request)", product.name
                )
            else:
                kept.append(product)
        return kept


# Future Enhancements:
# - Add a confidence gate: if fewer than half the LLM-selected names resolve to
#   catalog products, treat the response as hallucinated and trigger fallback.
# - Stream comparison replies to the client once the evaluator timeout allows it.
# - Log ShortlistPlan.reply to an evaluation trace store so prompt variants can
#   be compared offline without re-running the model.
