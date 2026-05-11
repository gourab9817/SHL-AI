from collections.abc import Mapping, Sequence


def build_assistant_history_content(
    content: str,
    recommendations: Sequence[Mapping[str, str]] | None = None,
) -> str:
    """Serialize assistant turns so stateless backends can recover prior shortlists.

    The API accepts only role/content messages. When the frontend displays
    recommendations separately from the assistant reply, we still need those
    product names preserved in the assistant content that gets sent back on the
    next turn. This helper appends a compact catalog summary for replay while
    keeping the visible UI unchanged.
    """
    normalized_content = content.strip()
    recommendation_lines: list[str] = []

    for recommendation in recommendations or ():
        name = str(recommendation.get("name", "")).strip()
        test_type = str(recommendation.get("test_type", "")).strip()
        if not name:
            continue
        suffix = f" [{test_type}]" if test_type else ""
        recommendation_lines.append(f"- {name}{suffix}")

    if not recommendation_lines:
        return normalized_content

    sections = [section for section in (normalized_content, "Catalog recommendations shared:", *recommendation_lines) if section]
    return "\n".join(sections)


# Future Enhancements:
# - Compress long assistant history into a structured summary once multi-turn
#   sessions grow large enough to threaten token budgets.
# - Add an API-facing serialization mode that includes stable entity IDs if the
#   evaluator contract ever allows assistant-side metadata.
