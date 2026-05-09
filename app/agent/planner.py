import logging

from app.catalog import CatalogIndex, CatalogProduct
from app.conversation import ConversationContext
from app.retrieval import CatalogRetriever, RetrievalResult
from app.retrieval.tokenizer import normalize_text
from app.schemas import ChatResponse, RecommendationItem

logger = logging.getLogger(__name__)


class ShortlistPlanner:
    """Creates catalog-safe shortlists from context, retrieval, and prior recommendations."""

    def __init__(self, catalog: CatalogIndex, retriever: CatalogRetriever) -> None:
        self.catalog = catalog
        self.retriever = retriever

    def build_query(self, context: ConversationContext) -> str:
        constraints = context.constraints
        parts = [
            context.latest_user_message,
            constraints.role_text or "",
            constraints.seniority or "",
            constraints.language or "",
            constraints.region_or_accent or "",
            constraints.use_case or "",
            " ".join(constraints.skills),
            " ".join(constraints.assessment_types),
        ]
        return " ".join(part for part in parts if part).strip()

    def plan_recommendation(self, context: ConversationContext, results: list[RetrievalResult]) -> list[CatalogProduct]:
        products = [result.product for result in results]
        if context.constraints.seniority == "senior" and context.constraints.skills:
            self._append_named(products, "SHL Verify Interactive G+")
            self._append_named(products, "Occupational Personality Questionnaire OPQ32r")
        return self._canonicalize(products)[:10]

    def plan_refinement(self, context: ConversationContext, results: list[RetrievalResult]) -> list[CatalogProduct]:
        products = list(context.previous_recommendations) or [result.product for result in results]
        removals = self._normalized_terms(context.actions.requested_removals)
        if removals:
            products = [product for product in products if not self._matches_any_removal(product, removals)]
        if context.actions.wants_shorter:
            products = self._prefer_shorter_products(products)

        for requested_addition in context.actions.requested_additions:
            if self._matches_any_text_removal(requested_addition, removals):
                continue

            exact_product = self.catalog.get_by_name(requested_addition)
            if exact_product is not None:
                products.append(exact_product)
            else:
                products.extend(result.product for result in self.retriever.search(requested_addition, limit=4))

        if not context.actions.requested_additions and results:
            for result in results[:3]:
                if not removals or not self._matches_any_removal(result.product, removals):
                    products.append(result.product)
        return self._canonicalize(products)[:10]

    def plan_finalization(self, context: ConversationContext) -> list[CatalogProduct]:
        return self._canonicalize(context.previous_recommendations)[:10]

    def build_response(self, *, reply: str, products: list[CatalogProduct], end_of_conversation: bool) -> ChatResponse:
        canonical_products = self._canonicalize(products)[:10]
        recommendations = [
            RecommendationItem(name=product.name, url=product.url, test_type=product.test_type)
            for product in canonical_products
            if product.url in self.catalog.url_whitelist
        ]
        if len(recommendations) != len(canonical_products):
            logger.warning("Dropped non-whitelisted recommendation during response build")
        return ChatResponse(reply=reply, recommendations=recommendations, end_of_conversation=end_of_conversation)

    def _append_named(self, products: list[CatalogProduct], product_name: str) -> None:
        product = self.catalog.get_by_name(product_name)
        if product is not None:
            products.append(product)

    def _canonicalize(self, products: list[CatalogProduct] | tuple[CatalogProduct, ...]) -> list[CatalogProduct]:
        seen: set[str] = set()
        canonical_products: list[CatalogProduct] = []
        for product in products:
            if product.entity_id in seen:
                continue
            seen.add(product.entity_id)
            canonical_products.append(product)
        return canonical_products

    def _normalized_terms(self, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_text(value) for value in values if normalize_text(value))

    def _matches_any_removal(self, product: CatalogProduct, removals: tuple[str, ...]) -> bool:
        normalized_product_name = normalize_text(product.name)
        return any(removal in normalized_product_name or normalized_product_name in removal for removal in removals)

    def _matches_any_text_removal(self, value: str, removals: tuple[str, ...]) -> bool:
        normalized_value = normalize_text(value)
        return any(removal in normalized_value or normalized_value in removal for removal in removals)

    def _prefer_shorter_products(self, products: list[CatalogProduct]) -> list[CatalogProduct]:
        return [product for product in products if product.name != "Occupational Personality Questionnaire OPQ32r"]
