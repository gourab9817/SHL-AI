import logging
import re
from collections.abc import Iterable

from app.catalog import CatalogIndex, CatalogProduct
from app.conversation.types import ConversationActions, ConversationConstraints, ConversationContext
from app.retrieval.tokenizer import normalize_text, tokenize
from app.schemas import Message

logger = logging.getLogger(__name__)


GREETING_PATTERNS = (
    "^hi$",
    "^hii$",
    "^hello$",
    "^hey$",
    "^howdy$",
    "^greetings$",
    "^hi there$",
    "^hello there$",
    "^good morning$",
    "^good afternoon$",
    "^good evening$",
)

# Matched anywhere in the message
IDENTITY_QUESTION_PATTERNS = (
    "who are you",
    "what are you",
    "what do you do",
    "what can you do",
    "tell me about yourself",
    "introduce yourself",
    "what is your purpose",
    "what are you for",
    "how can you help",
    "what can you help",
    "who is shl",
    "what is shl",
    "what does shl do",
    "explain yourself",
    "what is this",
    "what is this tool",
    "what are your capabilities",
)

# Only matched when the message STARTS WITH these (avoids false-positives like
# "developer who is senior" matching "who is")
IDENTITY_STARTSWITH_PATTERNS = (
    "who is ",
    "who was ",
    "who are ",
    "what is a ",
    "tell me about ",
)

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

FINAL_LIST_PATTERNS = (
    "final list",
    "final shortlist",
    "give me final list",
    "give me the final list",
    "show final list",
    "show me the final list",
    "share final list",
    "what is the final list",
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

        # role_text and seniority use ONLY the latest message so that switching roles
        # (e.g. "CISO" → "office boy") does not bleed the old role into the new query.
        # language/region/use_case accumulate because users clarify these progressively.
        return ConversationConstraints(
            role_text=self._extract_role_text(latest_user_message),
            seniority=self._latest_pattern_value(normalized_latest, SENIORITY_PATTERNS),
            skills=self._collect_pattern_values(normalized_latest, SKILL_PATTERNS),
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
            wants_shorter=self._contains_any_pattern(
                normalized_latest, ("shorter", "quick", "faster", "takes too long")
            ),
            says_no_preference=self._contains_any_pattern(normalized_latest, NO_PREFERENCE_PATTERNS),
            confirms_final=self._contains_any_pattern(normalized_latest, CONFIRMATION_PATTERNS),
            requests_final_list=self._contains_any_pattern(normalized_latest, FINAL_LIST_PATTERNS),
            asks_comparison=self._contains_any_pattern(normalized_latest, COMPARISON_PATTERNS),
            asks_recommendation=self._contains_any_pattern(
                normalized_latest, RECOMMENDATION_PATTERNS
            ),
            is_vague_request=self._is_vague_request(normalized_latest),
            has_job_description=self._has_job_description(latest_user_message, normalized_latest),
            is_greeting=self._is_greeting(normalized_latest),
            is_identity_question=self._is_identity_question(normalized_latest),
        )

    # Expanded role markers — must match at least one for a line to count as job context.
    _ROLE_MARKERS = (
        # Explicit hiring intent
        "hiring", "screening", "recruit", "candidate", "candidates",
        "assess", "assessment", "position", "vacancy", "opening", "role",
        # Seniority keywords
        "senior", "junior", "graduate", "trainee", "entry-level", "entry level",
        "mid-level", "mid level", "executive", "lead", "principal",
        # C-suite / leadership titles
        "ceo", "cto", "cfo", "coo", "cpo", "chro", "ciso",
        "vp ", "svp", "evp", "president", "vice president",
        "managing director", "general manager", "head of",
        # Job function / title words
        "engineer", "developer", "analyst", "designer", "scientist",
        "manager", "director", "coordinator", "administrator", "specialist",
        "consultant", "architect", "technician", "representative", "associate",
        "officer", "operator", "staff", "intern", "assistant",
        # Domain keywords
        "software", "data", "sales", "customer", "finance", "accounting",
        "marketing", "operations", "logistics", "supply chain", "legal",
        "hr", "human resources", "security", "devops", "cloud",
        # Tech skills — common enough to signal job context
        "java", "python", "sql", "aws", "react", "angular", "docker",
        "javascript", "typescript", "kubernetes", "linux", "rust",
        "go", "golang", "terraform", "azure", "gcp", "cloud", "devops",
        # Frontline / admin / clerical roles
        "admin", "administrative", "clerical", "clerk", "receptionist",
        "office", "support", "helpdesk", "assistant",
    )

    def _extract_role_text(self, full_user_text: str) -> str | None:
        """Return the most recent line that contains at least one role/hiring keyword.

        Returns None when no such line exists — callers must not treat a None
        role_text as evidence of hiring context.
        """
        lines = [line.strip(" >\"") for line in full_user_text.splitlines() if line.strip()]
        for line in reversed(lines):
            normalized_line = normalize_text(line)
            if self._line_has_role_marker(normalized_line):
                return line[:500]
        # No fallback — returning None signals "no job context detected".
        return None

    def _line_has_role_marker(self, normalized_line: str) -> bool:
        tokens = set(tokenize(normalized_line, keep_stopwords=True))
        if not tokens:
            return False

        for marker in self._ROLE_MARKERS:
            normalized_marker = normalize_text(marker)
            if " " in normalized_marker:
                if normalized_marker in normalized_line:
                    return True
            elif normalized_marker in tokens:
                return True
        return False

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
        if not self._contains_any_pattern(normalized_latest, action_words):
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

    def _contains_any_pattern(self, normalized_text: str, patterns: tuple[str, ...]) -> bool:
        return any(normalize_text(pattern) in normalized_text for pattern in patterns)

    def _is_greeting(self, normalized_latest: str) -> bool:
        """True when the entire message is a greeting with no job context."""
        import re as _re
        for pattern in GREETING_PATTERNS:
            if _re.fullmatch(normalize_text(pattern), normalized_latest.strip()):
                return True
        return False

    def _is_identity_question(self, normalized_latest: str) -> bool:
        """True when the user is asking who/what the agent is, about SHL, or about
        an external person/entity unrelated to hiring."""
        stripped = normalized_latest.strip()
        # Anywhere-match patterns
        if any(normalize_text(p) in normalized_latest for p in IDENTITY_QUESTION_PATTERNS):
            return True
        # Start-of-message patterns (avoids false positives inside longer sentences)
        if any(stripped.startswith(normalize_text(p)) for p in IDENTITY_STARTSWITH_PATTERNS):
            return True
        return False

    # Tokens that carry no hiring signal on their own
    _MEANINGLESS_TOKENS = frozenset({
        "what", "how", "why", "where", "when", "ok", "okay", "sure",
        "yes", "no", "maybe", "hmm", "hm", "um", "ah", "oh",
        "next", "more", "other", "another", "else",
    })

    def _is_vague_request(self, normalized_latest: str) -> bool:
        tokens = set(tokenize(normalized_latest))
        if not tokens:
            return True

        # Pure punctuation or single-char input ("?", ".", "!")
        if len(normalized_latest.strip()) <= 2:
            return True

        # Only meaningless filler words and no hiring signal
        if tokens and tokens.issubset(self._MEANINGLESS_TOKENS):
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
