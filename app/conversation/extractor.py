import logging
import re
from collections.abc import Iterable

from app.catalog import CatalogIndex, CatalogProduct
from app.conversation.types import ConversationActions, ConversationConstraints, ConversationContext
from app.retrieval.tokenizer import normalize_text, tokenize
from app.schemas import Message

logger = logging.getLogger(__name__)


CONFIRMATION_PATTERNS = (
    "confirmed",
    "confirm",
    "perfect",
    "that works",
    "that's good",
    "that covers it",
    "locking it in",
    "lock it in",
    "final list",
    "thanks",
)

RECOMMENDATION_PATTERNS = (
    "recommend",
    "assessment",
    "assessments",
    "battery",
    "shortlist",
    "what should",
    "what solutions",
)

COMPARISON_PATTERNS = (
    "difference between",
    "different from",
    "compare",
    "versus",
    " vs ",
)

NO_PREFERENCE_PATTERNS = (
    "no preference",
    "no strong preference",
    "doesn't matter",
    "dont care",
    "don't care",
)

ACTION_BOUNDARY_WORDS = (
    "add",
    "include",
    "also add",
    "drop",
    "remove",
    "exclude",
    "skip",
    "replace",
    "swap",
)

SENIORITY_PATTERNS = (
    ("executive", ("executive", "cxo", "cxos", "director", "leadership", "15 years")),
    ("senior", ("senior", "lead", "principal", "5+ years", "5 years", "10 years")),
    ("mid", ("mid-level", "mid level", "around 4 years", "4 years", "intermediate")),
    ("graduate", ("graduate", "graduates", "final-year", "final year", "trainee", "no work experience")),
    ("entry-level", ("entry-level", "entry level", "frontline", "front-line")),
)

LANGUAGE_PATTERNS = (
    ("Latin American Spanish", ("latin american spanish", "south texas", "spanish")),
    ("English (USA)", ("english us", "english usa", "us accent", "u.s. accent", "english.")),
    ("English", ("english",)),
)

REGION_OR_ACCENT_PATTERNS = (
    ("US accent", ("us accent", "u.s. accent", "english us", "english usa")),
    ("Indian accent", ("indian accent",)),
    ("UK accent", ("uk accent", "u.k.", "british")),
    ("Australian accent", ("australian", "aus accent")),
    ("South Texas", ("south texas",)),
)

USE_CASE_PATTERNS = (
    ("selection", ("selection", "hiring", "screening", "compare candidates")),
    ("development", ("development", "re-skill", "reskill", "talent audit", "annual talent audit")),
)

ASSESSMENT_TYPE_PATTERNS = (
    ("personality", ("personality", "behavioral", "behavioural", "opq")),
    ("cognitive", ("cognitive", "reasoning", "aptitude", "verify g", "g+")),
    ("situational judgment", ("situational judgement", "situational judgment", "sjt", "scenarios")),
    ("simulation", ("simulation", "simulations")),
    ("knowledge", ("knowledge", "skills", "domain test")),
)

SKILL_PATTERNS = (
    ("Core Java", ("core java", "java")),
    ("Spring", ("spring",)),
    ("REST API", ("rest api", "restful", "api design")),
    ("SQL", ("sql", "relational database", "relational databases")),
    ("AWS", ("aws", "amazon web services")),
    ("Docker", ("docker", "container")),
    ("Angular", ("angular",)),
    ("Rust", ("rust",)),
    ("Linux", ("linux",)),
    ("Networking", ("networking", "network infrastructure")),
    ("Excel", ("excel",)),
    ("Word", ("word",)),
    ("HIPAA", ("hipaa",)),
    ("Medical Terminology", ("medical terminology",)),
    ("Financial Accounting", ("financial accounting", "finance")),
    ("Statistics", ("statistics",)),
)


class ConversationContextExtractor:
    """Reconstructs agent-useful state from stateless chat history."""

    def __init__(self, catalog: CatalogIndex) -> None:
        self.catalog = catalog
        self._catalog_products_by_longest_name = tuple(
            sorted(catalog.products, key=lambda product: len(product.name), reverse=True)
        )
        logger.info("Conversation context extractor initialized")

    def extract(self, messages: Iterable[Message]) -> ConversationContext:
        message_list = tuple(messages)
        if not message_list:
            logger.error("Cannot extract context from empty message history")
            raise ValueError("message history cannot be empty")

        latest_user_message = self._latest_user_message(message_list)
        user_messages = tuple(message.content for message in message_list if message.role == "user")
        assistant_messages = tuple(message.content for message in message_list if message.role == "assistant")
        full_user_text = "\n".join(user_messages)
        latest_normalized = normalize_text(latest_user_message)

        previous_recommendations = self._extract_previous_recommendations(assistant_messages)
        mentioned_products = self._find_products_in_text("\n".join(message.content for message in message_list))
        comparison_products = self._extract_comparison_products(latest_user_message, mentioned_products)

        context = ConversationContext(
            latest_user_message=latest_user_message,
            user_turn_count=len(user_messages),
            assistant_turn_count=len(assistant_messages),
            total_turn_count=len(message_list),
            constraints=self._extract_constraints(full_user_text, latest_user_message),
            actions=self._extract_actions(latest_user_message, latest_normalized),
            mentioned_products=mentioned_products,
            previous_recommendations=previous_recommendations,
            comparison_products=comparison_products,
        )

        logger.info(
            "Extracted context: turns=%s, previous_recommendations=%s, comparison_products=%s",
            context.total_turn_count,
            len(context.previous_recommendations),
            len(context.comparison_products),
        )
        return context

    def _latest_user_message(self, messages: tuple[Message, ...]) -> str:
        for message in reversed(messages):
            if message.role == "user":
                return message.content
        logger.error("Message history has no user message")
        raise ValueError("message history must contain at least one user message")

    def _extract_constraints(self, full_user_text: str, latest_user_message: str) -> ConversationConstraints:
        normalized_full_text = normalize_text(full_user_text)
        normalized_latest = normalize_text(latest_user_message)

        return ConversationConstraints(
            role_text=self._extract_role_text(full_user_text),
            seniority=self._latest_pattern_value(normalized_full_text, SENIORITY_PATTERNS),
            skills=self._collect_pattern_values(normalized_full_text, SKILL_PATTERNS),
            language=self._latest_pattern_value(normalized_full_text, LANGUAGE_PATTERNS),
            region_or_accent=self._latest_pattern_value(normalized_full_text, REGION_OR_ACCENT_PATTERNS),
            use_case=self._latest_pattern_value(normalized_full_text, USE_CASE_PATTERNS),
            volume=self._extract_latest_volume(full_user_text),
            assessment_types=self._collect_pattern_values(normalized_latest, ASSESSMENT_TYPE_PATTERNS),
        )

    def _extract_actions(self, latest_user_message: str, normalized_latest: str) -> ConversationActions:
        return ConversationActions(
            requested_additions=self._extract_requested_items(latest_user_message, ("add", "include", "also add")),
            requested_removals=self._extract_requested_items(latest_user_message, ("drop", "remove", "exclude", "skip")),
            requested_replacements=self._extract_requested_items(latest_user_message, ("replace", "swap")),
            wants_shorter=any(term in normalized_latest for term in ("shorter", "quick", "faster", "takes too long")),
            says_no_preference=any(pattern in normalized_latest for pattern in NO_PREFERENCE_PATTERNS),
            confirms_final=any(pattern in normalized_latest for pattern in CONFIRMATION_PATTERNS),
            asks_comparison=any(pattern in normalized_latest for pattern in COMPARISON_PATTERNS),
            asks_recommendation=any(pattern in normalized_latest for pattern in RECOMMENDATION_PATTERNS),
            is_vague_request=self._is_vague_request(normalized_latest),
            has_job_description=self._has_job_description(latest_user_message, normalized_latest),
        )

    def _extract_role_text(self, full_user_text: str) -> str | None:
        lines = [line.strip(" >\"") for line in full_user_text.splitlines() if line.strip()]
        role_markers = ("hiring", "screening", "role", "engineer", "analyst", "assistant", "operator", "staff")
        for line in reversed(lines):
            normalized_line = normalize_text(line)
            if any(marker in normalized_line for marker in role_markers):
                return line[:500]
        return lines[-1][:500] if lines else None

    def _latest_pattern_value(self, normalized_text: str, patterns: tuple[tuple[str, tuple[str, ...]], ...]) -> str | None:
        latest_match: tuple[int, str] | None = None
        for value, phrases in patterns:
            for phrase in phrases:
                index = normalized_text.rfind(normalize_text(phrase))
                if index >= 0 and (latest_match is None or index > latest_match[0]):
                    latest_match = (index, value)
        return latest_match[1] if latest_match else None

    def _collect_pattern_values(
        self,
        normalized_text: str,
        patterns: tuple[tuple[str, tuple[str, ...]], ...],
    ) -> tuple[str, ...]:
        values: list[str] = []
        for value, phrases in patterns:
            if any(normalize_text(phrase) in normalized_text for phrase in phrases):
                values.append(value)
        return tuple(values)

    def _extract_latest_volume(self, text: str) -> int | None:
        matches = re.findall(r"\b(\d{2,6})\b", text)
        if not matches:
            return None
        return int(matches[-1])

    def _extract_requested_items(self, latest_user_message: str, action_words: tuple[str, ...]) -> tuple[str, ...]:
        normalized_latest = normalize_text(latest_user_message)
        if not any(action_word in normalized_latest for action_word in action_words):
            return ()

        product_names = self._extract_products_from_action_clause(normalized_latest, action_words)
        if product_names:
            return product_names

        tokens = tokenize(latest_user_message)
        action_tokens = {token for action_word in action_words for token in tokenize(action_word)}
        candidate_tokens = tuple(token for token in tokens if token not in action_tokens)
        return (" ".join(candidate_tokens[:6]),) if candidate_tokens else ()

    def _extract_products_from_action_clause(
        self,
        normalized_latest: str,
        action_words: tuple[str, ...],
    ) -> tuple[str, ...]:
        product_names: list[str] = []
        for action_word in action_words:
            normalized_action = normalize_text(action_word)
            action_index = normalized_latest.find(normalized_action)
            if action_index < 0:
                continue

            clause_start = action_index + len(normalized_action)
            clause_end = len(normalized_latest)
            for boundary_word in ACTION_BOUNDARY_WORDS:
                normalized_boundary = normalize_text(boundary_word)
                boundary_index = normalized_latest.find(normalized_boundary, clause_start)
                if boundary_index >= 0 and boundary_index < clause_end:
                    clause_end = boundary_index

            clause = normalized_latest[clause_start:clause_end]
            for product in self._catalog_products_by_longest_name:
                if normalize_text(product.name) in clause and product.name not in product_names:
                    product_names.append(product.name)

        return tuple(product_names)

    def _is_vague_request(self, normalized_latest: str) -> bool:
        tokens = set(tokenize(normalized_latest))
        if not tokens:
            return True
        vague_tokens = {"assessment", "assessments", "solution", "solutions", "test", "tests"}
        return bool(tokens & vague_tokens) and len(tokens - vague_tokens) <= 2

    def _has_job_description(self, latest_user_message: str, normalized_latest: str) -> bool:
        jd_signals = ("jd", "job description", "responsibilities", "required", "will own", "years across")
        return len(latest_user_message) > 250 or any(signal in normalized_latest for signal in jd_signals)

    def _extract_previous_recommendations(self, assistant_messages: tuple[str, ...]) -> tuple[CatalogProduct, ...]:
        for assistant_message in reversed(assistant_messages):
            products = self._find_products_in_text(assistant_message)
            if products:
                return products
        return ()

    def _extract_comparison_products(
        self,
        latest_user_message: str,
        mentioned_products: tuple[CatalogProduct, ...],
    ) -> tuple[CatalogProduct, ...]:
        products = self._find_products_in_text(latest_user_message)
        if len(products) >= 2:
            return products[:4]

        normalized_latest = normalize_text(latest_user_message)
        fallback_products: list[CatalogProduct] = list(products)
        if "opq" in normalized_latest:
            self._append_if_found(fallback_products, "Occupational Personality Questionnaire OPQ32r")
            self._append_if_found(fallback_products, "OPQ MQ Sales Report")
        if "gsa" in normalized_latest:
            self._append_if_found(fallback_products, "Global Skills Assessment")
        if "dsi" in normalized_latest:
            self._append_if_found(fallback_products, "Dependability and Safety Instrument (DSI)")
        if "safety and dependability" in normalized_latest or "8.0" in normalized_latest:
            self._append_if_found(fallback_products, "Manufac. & Indust. - Safety & Dependability 8.0")

        for product in mentioned_products:
            if product not in fallback_products and product.name in latest_user_message:
                fallback_products.append(product)

        return tuple(fallback_products[:4])

    def _append_if_found(self, products: list[CatalogProduct], product_name: str) -> None:
        product = self.catalog.get_by_name(product_name)
        if product is not None and product not in products:
            products.append(product)

    def _find_products_in_text(self, text: str) -> tuple[CatalogProduct, ...]:
        normalized_text = normalize_text(text)
        if not normalized_text:
            return ()

        products: list[CatalogProduct] = []
        occupied_spans: list[tuple[int, int]] = []

        for product in self._catalog_products_by_longest_name:
            normalized_name = normalize_text(product.name)
            match = re.search(rf"\b{re.escape(normalized_name)}\b", normalized_text)
            if match is None:
                continue
            span = match.span()
            if any(self._spans_overlap(span, occupied_span) for occupied_span in occupied_spans):
                continue
            products.append(product)
            occupied_spans.append(span)

        return tuple(products)

    def _spans_overlap(self, first: tuple[int, int], second: tuple[int, int]) -> bool:
        return first[0] < second[1] and second[0] < first[1]
