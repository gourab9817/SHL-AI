import pytest

from app.agent import AssessmentAgent
from app.catalog import load_catalog
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
async def test_agent_refuses_out_of_scope(agent: AssessmentAgent) -> None:
    response = await agent.chat(ChatRequest(messages=[Message(role="user", content="What salary should I offer?")]))

    assert response.recommendations == []
    assert response.end_of_conversation is False
    assert "salary" in response.reply.lower()
