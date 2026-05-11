import pytest

from app.agent import AssessmentAgent
from app.catalog import load_catalog
from app.chat_history import build_assistant_history_content
from app.conversation import ConversationContextExtractor
from app.guardrails import GuardrailService
from app.retrieval import CatalogRetriever
from app.schemas import ChatRequest, Message


@pytest.fixture()
def agent() -> AssessmentAgent:
    catalog = load_catalog()
    retriever = CatalogRetriever(catalog)
    return AssessmentAgent(
        catalog=catalog,
        retriever=retriever,
        context_extractor=ConversationContextExtractor(catalog),
        guardrail_service=GuardrailService(),
    )


@pytest.mark.anyio
async def test_agent_clarifies_vague_request(agent: AssessmentAgent) -> None:
    response = await agent.chat(ChatRequest(messages=[Message(role="user", content="I need an assessment")]))

    assert response.recommendations == []
    assert response.end_of_conversation is False
    assert "role" in response.reply.lower()


@pytest.mark.anyio
async def test_agent_recommends_from_catalog_for_backend_jd(agent: AssessmentAgent) -> None:
    response = await agent.chat(
        ChatRequest(
            messages=[
                Message(
                    role="user",
                    content=(
                        "Senior Full-Stack Engineer JD: Core Java, Spring, REST API, "
                        "SQL, AWS, Docker, backend microservice ownership."
                    ),
                )
            ]
        )
    )

    names = {item.name for item in response.recommendations}
    assert "Core Java (Advanced Level) (New)" in names
    assert "Spring (New)" in names
    assert "SQL (New)" in names
    assert all(item.url.startswith("https://www.shl.com/products/product-catalog/view/") for item in response.recommendations)


@pytest.mark.anyio
async def test_agent_clarifies_generic_senior_dev_without_skills(agent: AssessmentAgent) -> None:
    response = await agent.chat(ChatRequest(messages=[Message(role="user", content="a senior dev")]))

    assert response.recommendations == []
    assert "skills" in response.reply.lower() or "technologies" in response.reply.lower()


@pytest.mark.anyio
async def test_agent_refines_previous_shortlist(agent: AssessmentAgent) -> None:
    response = await agent.chat(
        ChatRequest(
            messages=[
                Message(role="user", content="Backend Java shortlist."),
                Message(
                    role="assistant",
                    content="Core Java (Advanced Level) (New), Spring (New), RESTful Web Services (New), SQL (New)",
                ),
                Message(role="user", content="Add Docker (New) and drop RESTful Web Services (New)."),
            ]
        )
    )

    names = {item.name for item in response.recommendations}
    assert "Docker (New)" in names
    assert "RESTful Web Services (New)" not in names


@pytest.mark.anyio
async def test_agent_refines_using_serialized_assistant_history(agent: AssessmentAgent) -> None:
    assistant_content = build_assistant_history_content(
        "These assessments cover the key technical skills you need.",
        [
            {"name": "Occupational Personality Questionnaire OPQ32r", "test_type": "P"},
            {"name": "SHL Verify Interactive G+", "test_type": "A"},
            {"name": "Core Java (Advanced Level) (New)", "test_type": "K"},
            {"name": "Docker (New)", "test_type": "K"},
            {"name": "Amazon Web Services (AWS) Development (New)", "test_type": "K"},
        ],
    )

    response = await agent.chat(
        ChatRequest(
            messages=[
                Message(role="user", content="a senior dev"),
                Message(role="assistant", content="What are the core skills or technologies this role needs?"),
                Message(role="user", content="with exp in java, docker, aws"),
                Message(role="assistant", content=assistant_content),
                Message(role="user", content="remove docker"),
            ]
        )
    )

    names = {item.name for item in response.recommendations}
    assert "Docker (New)" not in names
    assert "Core Java (Advanced Level) (New)" in names
    assert "Amazon Web Services (AWS) Development (New)" in names


@pytest.mark.anyio
async def test_agent_compares_without_recommending(agent: AssessmentAgent) -> None:
    response = await agent.chat(
        ChatRequest(
            messages=[
                Message(role="user", content="Sales audit stack."),
                Message(
                    role="assistant",
                    content="Occupational Personality Questionnaire OPQ32r and OPQ MQ Sales Report",
                ),
                Message(role="user", content="What is the difference between OPQ and OPQ MQ Sales Report?"),
            ]
        )
    )

    assert response.recommendations == []
    assert "Occupational Personality Questionnaire OPQ32r" in response.reply
    assert "OPQ MQ Sales Report" in response.reply


@pytest.mark.anyio
async def test_agent_finalizes_previous_shortlist(agent: AssessmentAgent) -> None:
    response = await agent.chat(
        ChatRequest(
            messages=[
                Message(role="user", content="Graduate trainee battery."),
                Message(
                    role="assistant",
                    content="SHL Verify Interactive G+, Occupational Personality Questionnaire OPQ32r, Graduate Scenarios",
                ),
                Message(role="user", content="Perfect, confirmed. Locking it in."),
            ]
        )
    )

    names = {item.name for item in response.recommendations}
    assert response.end_of_conversation is True
    assert "SHL Verify Interactive G+" in names
    assert "Graduate Scenarios" in names


@pytest.mark.anyio
async def test_agent_finalizes_when_user_asks_for_final_list(agent: AssessmentAgent) -> None:
    assistant_content = build_assistant_history_content(
        "Updated shortlist based on your latest constraints.",
        [
            {"name": "Core Java (Advanced Level) (New)", "test_type": "K"},
            {"name": "Amazon Web Services (AWS) Development (New)", "test_type": "K"},
            {"name": "Occupational Personality Questionnaire OPQ32r", "test_type": "P"},
        ],
    )

    response = await agent.chat(
        ChatRequest(
            messages=[
                Message(role="user", content="a senior dev"),
                Message(role="assistant", content="What are the core skills or technologies this role needs?"),
                Message(role="user", content="with exp in java, aws"),
                Message(role="assistant", content=assistant_content),
                Message(role="user", content="so give me final list"),
            ]
        )
    )

    names = {item.name for item in response.recommendations}
    assert response.end_of_conversation is True
    assert "Core Java (Advanced Level) (New)" in names
    assert "Amazon Web Services (AWS) Development (New)" in names


@pytest.mark.anyio
async def test_agent_clarifies_bare_confirmation_without_context(agent: AssessmentAgent) -> None:
    response = await agent.chat(ChatRequest(messages=[Message(role="user", content="That's good.")]))

    assert response.recommendations == []
    assert response.end_of_conversation is False
    assert "role" in response.reply.lower() or "assessment" in response.reply.lower()


@pytest.mark.anyio
async def test_agent_refuses_out_of_scope(agent: AssessmentAgent) -> None:
    response = await agent.chat(ChatRequest(messages=[Message(role="user", content="What salary should I offer?")]))

    assert response.recommendations == []
    assert response.end_of_conversation is False
    assert "salary" in response.reply.lower()
