import logging
from collections import Counter, defaultdict
from dataclasses import dataclass

from app.catalog import CatalogIndex, CatalogProduct
from app.retrieval.aliases import ALIAS_RULES, AliasRule
from app.retrieval.tokenizer import normalize_text, tokenize
from app.retrieval.types import RetrievalResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProductSearchProfile:
    product: CatalogProduct
    name_tokens: frozenset[str]
    description_tokens: frozenset[str]
    key_tokens: frozenset[str]
    job_level_tokens: frozenset[str]
    language_tokens: frozenset[str]
    normalized_name: str


class CatalogRetriever:
    """Deterministic hybrid retriever for the SHL product catalog."""

    def __init__(self, catalog: CatalogIndex) -> None:
        self.catalog = catalog
        self._profiles = tuple(self._build_profile(product) for product in catalog.products)
        logger.info("Catalog retriever initialized with %s product profiles", len(self._profiles))

    def search(self, query: str, *, limit: int = 10) -> list[RetrievalResult]:
        if limit <= 0:
            logger.warning("Received non-positive retrieval limit=%s; returning no results", limit)
            return []

        normalized_query = normalize_text(query)
        query_tokens = set(tokenize(query))
        if not normalized_query or not query_tokens:
            logger.info("Retrieval query was blank or tokenized to no searchable terms")
            return []

        alias_boosts, expansion_tokens = self._collect_alias_boosts(normalized_query)
        expanded_tokens = query_tokens | expansion_tokens
        scored_results = [
            result
            for profile in self._profiles
            if (result := self._score_profile(profile, normalized_query, expanded_tokens, alias_boosts))
            is not None
        ]

        scored_results.sort(key=lambda result: (-result.score, result.product.name))
        logger.info(
            "Retrieved %s result(s) for query length=%s with limit=%s",
            len(scored_results),
            len(query),
            limit,
        )
        return scored_results[:limit]

    def _build_profile(self, product: CatalogProduct) -> ProductSearchProfile:
        return ProductSearchProfile(
            product=product,
            name_tokens=frozenset(tokenize(product.name)),
            description_tokens=frozenset(tokenize(product.description)),
            key_tokens=frozenset(tokenize(" ".join(product.keys))),
            job_level_tokens=frozenset(tokenize(" ".join(product.job_levels))),
            language_tokens=frozenset(tokenize(" ".join(product.languages))),
            normalized_name=normalize_text(product.name),
        )

    def _collect_alias_boosts(
        self,
        normalized_query: str,
    ) -> tuple[dict[str, list[tuple[float, str]]], set[str]]:
        boosts: dict[str, list[tuple[float, str]]] = defaultdict(list)
        expansion_tokens: set[str] = set()

        for rule in ALIAS_RULES:
            if not self._rule_matches(rule, normalized_query):
                continue

            expansion_tokens.update(token for term in rule.expansion_terms for token in tokenize(term))
            for product_name in rule.product_names:
                product = self.catalog.get_by_name(product_name)
                if product is None:
                    logger.warning("Alias rule references unknown catalog product: %s", product_name)
                    continue
                boosts[product.entity_id].append((rule.boost, rule.reason))

        return boosts, expansion_tokens

    def _rule_matches(self, rule: AliasRule, normalized_query: str) -> bool:
        query_tokens = set(tokenize(normalized_query, keep_stopwords=True))
        for phrase in rule.phrases:
            normalized_phrase = normalize_text(phrase)
            phrase_tokens = set(tokenize(normalized_phrase, keep_stopwords=True))
            if normalized_phrase in normalized_query:
                return True
            if phrase_tokens and phrase_tokens.issubset(query_tokens):
                return True
        return False

    def _score_profile(
        self,
        profile: ProductSearchProfile,
        normalized_query: str,
        query_tokens: set[str],
        alias_boosts: dict[str, list[tuple[float, str]]],
    ) -> RetrievalResult | None:
        reasons: list[str] = []
        score = 0.0

        if profile.normalized_name in normalized_query:
            score += 120.0
            reasons.append("exact product name match")

        score += self._weighted_overlap(profile.name_tokens, query_tokens, 9.0, "name token", reasons)
        score += self._weighted_overlap(profile.description_tokens, query_tokens, 1.5, "description token", reasons)
        score += self._weighted_overlap(profile.key_tokens, query_tokens, 2.5, "assessment type token", reasons)
        score += self._weighted_overlap(profile.job_level_tokens, query_tokens, 2.0, "job level token", reasons)
        score += self._weighted_overlap(profile.language_tokens, query_tokens, 1.0, "language token", reasons)

        if profile.name_tokens and profile.name_tokens.issubset(query_tokens):
            score += 35.0
            reasons.append("all name tokens present")

        for boost, reason in alias_boosts.get(profile.product.entity_id, []):
            score += boost
            reasons.append(reason)

        if score <= 0:
            return None

        # Prefer actual assessments over report artifacts unless the query or aliases pull reports in.
        if "report" in profile.name_tokens and "report" not in query_tokens and not alias_boosts.get(profile.product.entity_id):
            score -= 12.0
            reasons.append("report artifact penalty")

        return RetrievalResult(
            product=profile.product,
            score=round(score, 3),
            reasons=tuple(self._compact_reasons(reasons)),
        )

    def _weighted_overlap(
        self,
        field_tokens: frozenset[str],
        query_tokens: set[str],
        weight: float,
        reason_prefix: str,
        reasons: list[str],
    ) -> float:
        matched_tokens = field_tokens & query_tokens
        if not matched_tokens:
            return 0.0

        top_tokens = ", ".join(sorted(matched_tokens)[:5])
        reasons.append(f"{reason_prefix} match: {top_tokens}")
        return len(matched_tokens) * weight

    def _compact_reasons(self, reasons: list[str]) -> list[str]:
        counts = Counter(reasons)
        return list(counts)
