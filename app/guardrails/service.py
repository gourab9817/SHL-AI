import logging

from app.conversation import ConversationContext
from app.guardrails.types import GuardrailDecision
from app.retrieval.tokenizer import normalize_text

logger = logging.getLogger(__name__)


PROMPT_INJECTION_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "ignore the above",
    "forget previous",
    "system prompt",
    "developer message",
    "you are now",
    "jailbreak",
    "dan mode",
    "act as dan",
    "reveal your instructions",
    "print your instructions",
    "bypass",
    "override",
    "invent a url",
    "fake url",
    "make up a url",
)

LEGAL_PATTERNS = (
    "legally required",
    "legal requirement",
    "required under",
    "satisfy that requirement",
    "satisfies that requirement",
    "satisfy legal",
    "compliance obligation",
    "regulatory obligation",
    "employment law",
    "discrimination law",
    "is it legal",
    "legally compliant",
)

GENERAL_HIRING_PATTERNS = (
    "what salary",
    "salary should",
    "compensation",
    "offer letter",
    "where should i post",
    "sourcing strategy",
    "interview questions",
    "interview process",
    "background check",
    "fire an employee",
    "terminate an employee",
)

NON_SHL_PATTERNS = (
    "hackerrank",
    "codility",
    "testgorilla",
    "wonderlic",
    "mercer mettl",
    "criteria corp",
    "non shl",
    "non-shl",
    "outside shl",
)

OFF_TOPIC_PATTERNS = (
    "weather",
    "stock price",
    "recipe",
    "travel itinerary",
    "write code",
    "debug my code",
)

ASSESSMENT_SCOPE_PATTERNS = (
    "shl",
    "assessment",
    "assessments",
    "test",
    "tests",
    "battery",
    "shortlist",
    "catalog",
    "opq",
    "gsa",
    "verify",
    "svar",
    "dsi",
    "recommend",
    "compare",
    "difference between",
)


class GuardrailService:
    """Deterministic scope guard for the SHL assessment recommender."""

    def evaluate(self, context: ConversationContext) -> GuardrailDecision:
        normalized_message = normalize_text(context.latest_user_message)

        if self._matches(normalized_message, PROMPT_INJECTION_PATTERNS):
            logger.warning("Refusing prompt-injection attempt")
            return GuardrailDecision.refuse(
                "prompt_injection",
                "User attempted to override system/catalog constraints.",
                (
                    "I can't follow instructions that override the SHL catalog or response rules. "
                    "I can help select or compare SHL assessments using catalog-backed information."
                ),
            )

        if self._is_legal_or_compliance_question(normalized_message):
            logger.info("Refusing legal/compliance advice request")
            return GuardrailDecision.refuse(
                "legal_or_compliance",
                "User asked for legal or regulatory advice.",
                (
                    "I can't provide legal or compliance advice. I can help identify SHL assessments "
                    "that measure relevant skills or knowledge, but your legal or compliance team "
                    "should decide whether a test satisfies any regulatory obligation."
                ),
            )

        if self._matches(normalized_message, NON_SHL_PATTERNS):
            logger.info("Refusing non-SHL assessment request")
            return GuardrailDecision.refuse(
                "non_shl_assessment",
                "User asked for non-SHL or out-of-catalog assessments.",
                (
                    "I can only recommend assessments from the SHL product catalog. Share the role, "
                    "skills, seniority, and language needs, and I'll shortlist catalog-backed SHL options."
                ),
            )

        if self._matches(normalized_message, GENERAL_HIRING_PATTERNS):
            logger.info("Refusing general hiring advice request")
            return GuardrailDecision.refuse(
                "general_hiring_advice",
                "User asked for hiring advice outside assessment selection.",
                (
                    "I can help with SHL assessment selection, but not general hiring advice such as "
                    "salary, sourcing, interview process design, or employment decisions."
                ),
            )

        if self._is_clearly_off_topic(normalized_message):
            logger.info("Refusing off-topic request")
            return GuardrailDecision.refuse(
                "off_topic",
                "User request is unrelated to SHL assessments.",
                (
                    "I can only help with SHL assessment recommendations and catalog-backed comparisons. "
                    "Please share the role or assessment need you want to evaluate."
                ),
            )

        return GuardrailDecision.allow()

    def _is_legal_or_compliance_question(self, normalized_message: str) -> bool:
        if not self._matches(normalized_message, LEGAL_PATTERNS):
            return False

        # Product-selection mentions of HIPAA are allowed unless framed as a legal obligation.
        return True

    def _is_clearly_off_topic(self, normalized_message: str) -> bool:
        if not self._matches(normalized_message, OFF_TOPIC_PATTERNS):
            return False
        return not self._matches(normalized_message, ASSESSMENT_SCOPE_PATTERNS)

    def _matches(self, normalized_message: str, patterns: tuple[str, ...]) -> bool:
        return any(normalize_text(pattern) in normalized_message for pattern in patterns)
