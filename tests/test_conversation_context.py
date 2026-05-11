from app.catalog import load_catalog
from app.conversation import ConversationContextExtractor
from app.schemas import Message


def _extract(messages: list[Message]):
    return ConversationContextExtractor(load_catalog()).extract(messages)


def test_context_extracts_latest_user_message_and_turn_counts() -> None:
    context = _extract(
        [
            Message(role="user", content="We need a solution for senior leadership."),
            Message(role="assistant", content="Who is this meant for?"),
            Message(role="user", content="CXOs and director-level people."),
        ]
    )

    assert context.latest_user_message == "CXOs and director-level people."
    assert context.user_turn_count == 2
    assert context.assistant_turn_count == 1
    assert context.total_turn_count == 3
    assert context.remaining_turn_budget == 5


def test_context_detects_vague_request() -> None:
    context = _extract([Message(role="user", content="I need an assessment")])

    assert context.actions.is_vague_request is True
    assert context.actions.asks_recommendation is True


def test_context_extracts_job_description_skills_and_seniority() -> None:
    context = _extract(
        [
            Message(
                role="user",
                content=(
                    "Senior Full-Stack Engineer JD: 5+ years across Core Java, "
                    "Spring, REST API design, Angular, SQL, AWS, and Docker. "
                    "Will own microservice delivery."
                ),
            )
        ]
    )

    assert context.actions.has_job_description is True
    assert context.constraints.seniority == "senior"
    assert {"Core Java", "Spring", "REST API", "SQL", "AWS", "Docker"}.issubset(
        set(context.constraints.skills)
    )


def test_context_recovers_previous_recommendations_from_assistant_text() -> None:
    context = _extract(
        [
            Message(role="user", content="Hiring graduate financial analysts."),
            Message(
                role="assistant",
                content=(
                    "| Name | URL |\n"
                    "| SHL Verify Interactive – Numerical Reasoning | https://www.shl.com/... |\n"
                    "| Financial Accounting (New) | https://www.shl.com/... |\n"
                    "| Basic Statistics (New) | https://www.shl.com/... |"
                ),
            ),
            Message(role="user", content="Add Graduate Scenarios."),
        ]
    )

    previous_names = {product.name for product in context.previous_recommendations}

    assert "SHL Verify Interactive – Numerical Reasoning" in previous_names
    assert "Financial Accounting (New)" in previous_names
    assert "Basic Statistics (New)" in previous_names


def test_context_detects_add_and_drop_refinements() -> None:
    context = _extract(
        [
            Message(role="user", content="Recommend for backend Java."),
            Message(
                role="assistant",
                content=(
                    "Core Java (Advanced Level) (New), Spring (New), "
                    "RESTful Web Services (New), SQL (New)"
                ),
            ),
            Message(role="user", content="Add Docker (New) and drop RESTful Web Services (New)."),
        ]
    )

    assert "Docker (New)" in context.actions.requested_additions
    assert "RESTful Web Services (New)" in context.actions.requested_removals


def test_context_detects_comparison_aliases() -> None:
    context = _extract(
        [
            Message(role="user", content="Sales audit stack."),
            Message(
                role="assistant",
                content="Occupational Personality Questionnaire OPQ32r and OPQ MQ Sales Report",
            ),
            Message(role="user", content="What's the difference between OPQ and OPQ MQ Sales Report?"),
        ]
    )

    comparison_names = {product.name for product in context.comparison_products}

    assert context.actions.asks_comparison is True
    assert "Occupational Personality Questionnaire OPQ32r" in comparison_names
    assert "OPQ MQ Sales Report" in comparison_names


def test_context_detects_confirmation_and_no_preference() -> None:
    context = _extract(
        [
            Message(role="user", content="No preference on language."),
            Message(role="assistant", content="Here is a shortlist."),
            Message(role="user", content="Perfect, confirmed. Locking it in."),
        ]
    )

    assert context.actions.confirms_final is True

    earlier_context = _extract([Message(role="user", content="No preference on language.")])
    assert earlier_context.actions.says_no_preference is True


def test_context_detects_explicit_final_list_request() -> None:
    context = _extract([Message(role="user", content="So give me the final list.")])

    assert context.actions.requests_final_list is True


def test_context_detects_confirmation_with_punctuation_normalization() -> None:
    context = _extract(
        [
            Message(role="user", content="I need to quickly screen admin assistants for Excel and Word daily."),
            Message(
                role="assistant",
                content=(
                    "Updated shortlist with simulations: "
                    "Microsoft Excel 365 (New), "
                    "Microsoft Word 365 (New), "
                    "MS Excel (New), "
                    "MS Word (New), "
                    "Occupational Personality Questionnaire OPQ32r."
                ),
            ),
            Message(role="user", content="That's good."),
        ]
    )

    assert context.actions.confirms_final is True
    previous_names = {product.name for product in context.previous_recommendations}
    assert "Microsoft Excel 365 (New)" in previous_names
    assert "MS Word (New)" in previous_names
    assert context.constraints.role_text is None


def test_context_does_not_treat_generic_confirmation_as_role_text() -> None:
    context = _extract([Message(role="user", content="That's good.")])

    assert context.constraints.role_text is None
    assert context.actions.confirms_final is True


def test_context_prefers_latest_constraint_when_user_corrects_seniority() -> None:
    context = _extract(
        [
            Message(role="user", content="Hiring graduate Java developers."),
            Message(role="assistant", content="Okay."),
            Message(role="user", content="Actually this is a senior IC role with 5+ years."),
        ]
    )

    assert context.constraints.seniority == "senior"


def test_context_extracts_language_region_and_volume() -> None:
    context = _extract(
        [
            Message(
                role="user",
                content="We're screening 500 entry-level contact centre agents. English US accent.",
            )
        ]
    )

    assert context.constraints.volume == 500
    assert context.constraints.language == "English (USA)"
    assert context.constraints.region_or_accent == "US accent"
