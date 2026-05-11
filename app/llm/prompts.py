"""Grounded prompt builders for every LLM call in the agent.

All prompts share three invariants:
1. The model is never given product URLs — URLs are always resolved from the
   catalog after the model returns names, preventing hallucinated links.
2. Catalog content is the only allowed information source. System prompts
   explicitly forbid the model from using its training knowledge about SHL.
3. Each builder returns a list[dict] ready for the Groq messages parameter,
   so callers stay decoupled from prompt internals.
"""
from typing import Literal

from app.catalog.models import CatalogProduct
from app.conversation.types import ConversationContext

# ------------------------------------------------------------------ #
# Shared constants                                                     #
# ------------------------------------------------------------------ #

_SCOPE_REMINDER = (
    "You are an expert SHL assessment consultant. "
    "You ONLY discuss SHL assessments from the catalog provided to you. "
    "Do not use your training knowledge about SHL products — "
    "rely exclusively on the catalog data in this prompt."
)

_MAX_CANDIDATE_DESCRIPTION_CHARS = 180


# ------------------------------------------------------------------ #
# Shortlist selection (recommend + refine) — JSON output             #
# ------------------------------------------------------------------ #

_SHORTLIST_SYSTEM = """\
{scope}

Your task is to select the most appropriate SHL assessments for the hiring context below.

RULES — follow exactly:
- Select ONLY from the CANDIDATE ASSESSMENTS list. Never invent a product name.
- Copy product names character-for-character from the list. Spelling errors cause lookup failures.
- Select between 1 and 10 assessments.
- Always include a personality measure (Occupational Personality Questionnaire OPQ32r) \
for professional, senior, or leadership roles unless the user explicitly excluded it.
- Always include a cognitive ability test (SHL Verify Interactive G+) for senior IC roles \
and above unless the user explicitly excluded it.
- For graduate roles, prefer Graduate Scenarios as the situational-judgment component.
- Respect every explicit exclusion or removal the user stated.
- CRITICAL — Knowledge/skills tests (test type K): ONLY include a knowledge test if the \
specific technology or subject it measures is explicitly stated in the HIRING CONTEXT below. \
For example: do NOT include a Java test when the role is Python; do NOT include an Excel test \
when the role is software engineering. If the candidate list includes irrelevant skill tests, \
skip them entirely.

Return a JSON object with exactly these two keys:
{{
  "selected_names": ["Exact Product Name 1", "Exact Product Name 2"],
  "reply": "2-3 sentence recruiter-friendly explanation of why these were chosen."
}}
""".format(scope=_SCOPE_REMINDER)

_REFINE_ADDITION = """\

REFINEMENT INSTRUCTION:
The hiring manager already has a shortlist. Update it based on their latest request.
- Start from the CURRENT SHORTLIST shown below; do not restart from scratch.
- Apply all add / drop / replace instructions from the user.
- If the user said "make it shorter", remove the least relevant items.
- The updated list must remain between 1 and 10 items.
"""


def build_shortlist_messages(
    context: ConversationContext,
    candidates: list[CatalogProduct],
    intent: Literal["recommend", "refine"],
) -> list[dict[str, str]]:
    """Build the messages for a combined product-selection + reply-text JSON call."""
    system = _SHORTLIST_SYSTEM
    if intent == "refine":
        system += _REFINE_ADDITION

    user_parts: list[str] = []

    user_parts.append("CANDIDATE ASSESSMENTS (select only from this list):\n")
    for i, product in enumerate(candidates, start=1):
        description_snippet = (product.description or "")[:_MAX_CANDIDATE_DESCRIPTION_CHARS]
        if len(product.description or "") > _MAX_CANDIDATE_DESCRIPTION_CHARS:
            description_snippet += "…"
        keys_label = ", ".join(product.keys) if product.keys else "Unspecified"
        levels_label = ", ".join(product.job_levels[:3]) if product.job_levels else "General"
        duration_label = product.duration or "Duration not listed"
        user_parts.append(
            f"[{i}] {product.name}\n"
            f"    Type: {keys_label} | {duration_label} | For: {levels_label}\n"
            f"    {description_snippet}\n"
        )

    if intent == "refine" and context.previous_recommendations:
        user_parts.append("\nCURRENT SHORTLIST:\n")
        for product in context.previous_recommendations:
            user_parts.append(f"- {product.name}\n")

    user_parts.append("\nHIRING CONTEXT:\n")
    constraints = context.constraints
    if constraints.role_text:
        user_parts.append(f"Role: {constraints.role_text}\n")
    if constraints.seniority:
        user_parts.append(f"Seniority: {constraints.seniority}\n")
    if constraints.skills:
        user_parts.append(f"Skills required: {', '.join(constraints.skills)}\n")
    if constraints.language:
        user_parts.append(f"Language: {constraints.language}\n")
    if constraints.region_or_accent:
        user_parts.append(f"Region / accent: {constraints.region_or_accent}\n")
    if constraints.use_case:
        user_parts.append(f"Purpose: {constraints.use_case}\n")
    if constraints.volume:
        user_parts.append(f"Candidate volume: {constraints.volume}\n")
    if constraints.assessment_types:
        user_parts.append(f"Requested assessment types: {', '.join(constraints.assessment_types)}\n")

    if intent == "refine":
        actions = context.actions
        if actions.requested_additions:
            user_parts.append(f"ADD: {', '.join(actions.requested_additions)}\n")
        if actions.requested_removals:
            user_parts.append(f"DROP: {', '.join(actions.requested_removals)}\n")
        if actions.requested_replacements:
            user_parts.append(f"REPLACE: {', '.join(actions.requested_replacements)}\n")
        if actions.wants_shorter:
            user_parts.append("USER WANTS A SHORTER LIST — remove the least relevant items.\n")

    user_parts.append(
        f"\nLatest user message: \"{context.latest_user_message}\"\n"
    )
    user_parts.append(
        "\nNow return the JSON object with selected_names and reply."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "".join(user_parts)},
    ]


# ------------------------------------------------------------------ #
# Clarification question — free text                                   #
# ------------------------------------------------------------------ #

_CLARIFY_SYSTEM = """\
{scope}

The hiring manager has not provided enough information to make an assessment recommendation.
Ask ONE focused clarifying question about the single most important missing detail.

Priority order — ask about the first item that is unknown:
1. Job role or function (if completely unspecified)
2. Seniority level or years of experience
3. Language or region requirements (if the workforce is likely multilingual)
4. Purpose: selection (new hire) or development (upskilling existing employees)?

Rules:
- Ask exactly ONE question. One sentence only.
- Conversational and professional tone.
- Do not explain why you are asking.
- Do not offer multiple-choice options.
- Do not recommend assessments yet.
""".format(scope=_SCOPE_REMINDER)


def build_clarify_messages(context: ConversationContext) -> list[dict[str, str]]:
    """Build the messages for a clarifying-question generation call."""
    lines: list[str] = ["The recruiter said:\n"]
    lines.append(f'"{context.latest_user_message}"\n')

    constraints = context.constraints
    known_parts: list[str] = []
    if constraints.role_text:
        known_parts.append(f"role: {constraints.role_text}")
    if constraints.seniority:
        known_parts.append(f"seniority: {constraints.seniority}")
    if constraints.skills:
        known_parts.append(f"skills: {', '.join(constraints.skills)}")
    if constraints.language:
        known_parts.append(f"language: {constraints.language}")
    if constraints.use_case:
        known_parts.append(f"purpose: {constraints.use_case}")

    if known_parts:
        lines.append(f"\nAlready known: {'; '.join(known_parts)}.\n")

    lines.append(
        "\nWhat is the single most important clarifying question to ask next?"
    )

    return [
        {"role": "system", "content": _CLARIFY_SYSTEM},
        {"role": "user", "content": "".join(lines)},
    ]


# ------------------------------------------------------------------ #
# Product comparison — free text                                       #
# ------------------------------------------------------------------ #

_COMPARE_SYSTEM = """\
{scope}

The hiring manager wants to understand the difference between two or more SHL assessments.
Write a concise, structured comparison using ONLY the catalog information provided below.

Rules:
- Use ONLY the product details shown. Do not add anything from your training knowledge.
- Explain: what each product measures, the key difference in purpose or format, \
and which hiring scenario each suits best.
- Keep the response under 180 words.
- Use plain prose — no bullet lists, no headers.
- Do not recommend one over the other unless the user's context clearly favours one.
""".format(scope=_SCOPE_REMINDER)


def build_compare_messages(
    context: ConversationContext,
    products: tuple[CatalogProduct, ...],
) -> list[dict[str, str]]:
    """Build the messages for a grounded product-comparison call."""
    product_lines: list[str] = ["PRODUCTS TO COMPARE:\n\n"]
    for product in products:
        keys_label = ", ".join(product.keys) if product.keys else "Unspecified"
        levels_label = (
            ", ".join(product.job_levels[:4]) if product.job_levels else "General population"
        )
        langs = ", ".join(product.languages[:5]) if product.languages else "See catalog"
        if len(product.languages) > 5:
            langs += f" (+{len(product.languages) - 5} more)"
        product_lines.append(
            f"Product: {product.name}\n"
            f"Type: {keys_label}\n"
            f"Duration: {product.duration or 'Not listed'}\n"
            f"Job levels: {levels_label}\n"
            f"Languages: {langs}\n"
            f"Description: {product.description or 'No description available.'}\n\n"
        )

    product_lines.append(
        f"Recruiter's question: \"{context.latest_user_message}\"\n\n"
        "Write a concise grounded comparison now."
    )

    return [
        {"role": "system", "content": _COMPARE_SYSTEM},
        {"role": "user", "content": "".join(product_lines)},
    ]


# Future Enhancements:
# - Externalise prompts to YAML/TOML so non-engineers can iterate on wording
#   without touching Python source files.
# - Add a prompt-version field to each builder so offline evaluation traces
#   can be tied back to the exact prompt revision that generated them.
# - Introduce few-shot examples into shortlist selection for niche roles
#   (e.g. aviation, legal) that the alias dictionary does not cover.
