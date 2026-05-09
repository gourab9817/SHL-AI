"""Post-generation output verifier for catalog integrity and schema compliance.

This module is the last line of defense before a response leaves the agent.
It catches anything that the generation layer allowed through and either
repairs it or strips it — the response returned from here is always
schema-valid and catalog-grounded.

Invariants enforced:
1. Intents that must never carry recommendations (clarify, refuse, compare) get
   an empty list regardless of what the generation layer produced.
2. Every recommendation URL must be in the catalog whitelist.
3. Every recommendation name and test_type is re-derived from the matched
   catalog product — the LLM-emitted values are never trusted directly.
4. Recommendation count is capped at 10.
5. end_of_conversation is True only when the finalize intent has surviving
   recommendations.
"""
import logging

from app.catalog import CatalogIndex
from app.schemas import ChatResponse, RecommendationItem

logger = logging.getLogger(__name__)

_EMPTY_REC_INTENTS = frozenset({"clarify", "refuse", "compare"})


class ResponseVerifier:
    """Validates and repairs ChatResponse objects before they leave the agent."""

    def __init__(self, catalog: CatalogIndex) -> None:
        self._catalog = catalog

    def verify(self, response: ChatResponse, intent: str) -> ChatResponse:
        """Return a catalog-safe, schema-valid version of *response*.

        Never raises. If a recommendation cannot be verified it is silently
        dropped; the caller receives whatever survives.
        """
        if intent in _EMPTY_REC_INTENTS:
            return self._enforce_empty_recommendations(response, intent)

        verified_recs = self._verify_recommendations(response.recommendations)

        end_of_conversation = response.end_of_conversation
        if end_of_conversation and not verified_recs:
            logger.warning(
                "Verifier cleared end_of_conversation=True — no valid recommendations remain "
                "after verification (intent=%s)",
                intent,
            )
            end_of_conversation = False

        return ChatResponse(
            reply=response.reply,
            recommendations=verified_recs,
            end_of_conversation=end_of_conversation,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _enforce_empty_recommendations(self, response: ChatResponse, intent: str) -> ChatResponse:
        if response.recommendations:
            logger.warning(
                "Verifier stripped %d recommendation(s) from %s response",
                len(response.recommendations),
                intent,
            )
        return ChatResponse(
            reply=response.reply,
            recommendations=[],
            end_of_conversation=False,
        )

    def _verify_recommendations(
        self, recommendations: list[RecommendationItem]
    ) -> list[RecommendationItem]:
        verified: list[RecommendationItem] = []
        seen_entity_ids: set[str] = set()

        for rec in recommendations:
            if rec.url not in self._catalog.url_whitelist:
                logger.warning(
                    "Verifier dropped recommendation with non-whitelisted URL: %r (name=%r)",
                    rec.url,
                    rec.name,
                )
                continue

            product = self._catalog.get_by_url(rec.url)
            if product is None:
                logger.warning(
                    "Verifier dropped recommendation — URL in whitelist but not found in index: %r",
                    rec.url,
                )
                continue

            if product.entity_id in seen_entity_ids:
                logger.debug("Verifier deduplicated recommendation: %r", product.name)
                continue

            seen_entity_ids.add(product.entity_id)
            verified.append(
                RecommendationItem(
                    name=product.name,
                    url=product.url,
                    test_type=product.test_type,
                )
            )

        if len(verified) > 10:
            logger.warning(
                "Verifier trimmed recommendation list from %d to 10", len(verified)
            )
            verified = verified[:10]

        if len(verified) != len(recommendations):
            logger.info(
                "Verifier: %d/%d recommendations passed validation",
                len(verified),
                len(recommendations),
            )

        return verified


# Future Enhancements:
# - Add a name-mismatch warning (LLM name differs from catalog name by edit distance)
#   without failing so the name in the response always comes from the catalog.
# - Track verification failure rates per intent in structured logs for regression
#   monitoring without re-running the full test suite.
# - Add a reply-length guard (e.g. max 1000 chars) as a latency proxy for overly
#   verbose LLM replies.
