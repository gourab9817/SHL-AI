from dataclasses import dataclass
from typing import Literal


GuardrailCategory = Literal[
    "allowed",
    "legal_or_compliance",
    "prompt_injection",
    "general_hiring_advice",
    "non_shl_assessment",
    "off_topic",
]


@dataclass(frozen=True)
class GuardrailDecision:
    is_allowed: bool
    category: GuardrailCategory
    reason: str
    reply: str | None = None

    @classmethod
    def allow(cls, reason: str = "in scope") -> "GuardrailDecision":
        return cls(is_allowed=True, category="allowed", reason=reason)

    @classmethod
    def refuse(cls, category: GuardrailCategory, reason: str, reply: str) -> "GuardrailDecision":
        return cls(is_allowed=False, category=category, reason=reason, reply=reply)
