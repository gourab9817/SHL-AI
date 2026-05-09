"""Typed results returned by Groq LLM calls before catalog validation."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShortlistPlan:
    """Structured output from an LLM shortlist-selection call.

    Names are raw strings from the model. They must be validated against the
    catalog before any URL or test_type is derived from them.
    """

    selected_names: tuple[str, ...]
    reply: str

    @classmethod
    def from_llm_dict(cls, data: dict[str, Any]) -> "ShortlistPlan":
        """Parse the JSON object returned by the model.

        Tolerates missing or wrongly-typed fields so a partially valid LLM
        response still yields a usable plan rather than crashing.
        """
        raw_names = data.get("selected_names", [])
        if not isinstance(raw_names, list):
            raw_names = []

        cleaned_names = tuple(
            str(n).strip()
            for n in raw_names
            if isinstance(n, str) and str(n).strip()
        )

        reply = str(data.get("reply", "")).strip()
        return cls(selected_names=cleaned_names, reply=reply)

    @property
    def is_valid(self) -> bool:
        """True only when the plan has at least one candidate and a reply."""
        return bool(self.selected_names) and bool(self.reply)


# Future Enhancements:
# - Add a confidence score per selected name to support ranked filtering.
# - Support a structured "reasoning" field so generation traces can be logged
#   for offline evaluation without re-running the model.
