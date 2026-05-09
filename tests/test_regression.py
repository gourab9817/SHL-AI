"""Regression harness for C1-C10 public sample conversations.

Tests run in deterministic mode (no LLM generator) so they pass without a
GROQ_API_KEY and produce stable, repeatable results. The Recall@10 metric
measures how many of the expected final products appear in the agent's
response for each trace.

What this harness catches:
- Schema regressions: any response that fails Pydantic validation.
- Catalog leakage: URLs not in the catalog whitelist.
- Recall drops: a code change that reduces retrieval or planning quality.
- Behavioral regressions: clarify/refuse paths producing recommendations.
"""
import logging

import pytest

from app.agent import AssessmentAgent
from app.catalog import load_catalog
from app.conversation import ConversationContextExtractor
from app.guardrails import GuardrailService
from app.retrieval import CatalogRetriever
from app.schemas import ChatRequest, ChatResponse, Message
from tests.fixtures import CONVERSATION_FIXTURES, ConversationFixture

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Shared fixtures                                                      #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def agent(catalog) -> AssessmentAgent:
    return AssessmentAgent(
        catalog=catalog,
        retriever=CatalogRetriever(catalog),
        context_extractor=ConversationContextExtractor(catalog),
        guardrail_service=GuardrailService(),
    )


# ------------------------------------------------------------------ #
# Recall metric                                                        #
# ------------------------------------------------------------------ #

def recall_at_k(recommended_names: set[str], expected_names: frozenset[str]) -> float:
    """Fraction of expected products found in the recommendation set.

    Returns 0.0 if expected_names is empty (undefined recall).
    """
    if not expected_names:
        return 0.0
    hits = len(recommended_names & expected_names)
    return hits / len(expected_names)


# ------------------------------------------------------------------ #
# Parametrized regression tests                                        #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
@pytest.mark.parametrize(
    "fixture",
    CONVERSATION_FIXTURES,
    ids=[f.name for f in CONVERSATION_FIXTURES],
)
async def test_regression_schema_valid(fixture: ConversationFixture, agent: AssessmentAgent, catalog) -> None:
    """Every response must be schema-valid with non-null recommendations list."""
    request = ChatRequest(messages=[Message(role=r, content=c) for r, c in fixture.messages])
    response = await agent.chat(request)

    assert isinstance(response, ChatResponse)
    assert isinstance(response.reply, str) and len(response.reply) > 0
    assert isinstance(response.recommendations, list)
    assert isinstance(response.end_of_conversation, bool)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fixture",
    CONVERSATION_FIXTURES,
    ids=[f.name for f in CONVERSATION_FIXTURES],
)
async def test_regression_all_urls_whitelisted(fixture: ConversationFixture, agent: AssessmentAgent, catalog) -> None:
    """Every recommendation URL must be in the catalog whitelist."""
    request = ChatRequest(messages=[Message(role=r, content=c) for r, c in fixture.messages])
    response = await agent.chat(request)

    for rec in response.recommendations:
        assert rec.url in catalog.url_whitelist, (
            f"[{fixture.name}] Non-whitelisted URL in response: {rec.url!r} for product {rec.name!r}"
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fixture",
    CONVERSATION_FIXTURES,
    ids=[f.name for f in CONVERSATION_FIXTURES],
)
async def test_regression_recommendation_count(fixture: ConversationFixture, agent: AssessmentAgent) -> None:
    """When recommendations are present they must be between 1 and 10."""
    request = ChatRequest(messages=[Message(role=r, content=c) for r, c in fixture.messages])
    response = await agent.chat(request)

    if response.recommendations:
        assert 1 <= len(response.recommendations) <= 10, (
            f"[{fixture.name}] Invalid recommendation count: {len(response.recommendations)}"
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fixture",
    CONVERSATION_FIXTURES,
    ids=[f.name for f in CONVERSATION_FIXTURES],
)
async def test_regression_recall_at_10(fixture: ConversationFixture, agent: AssessmentAgent) -> None:
    """Recall@10 must meet the per-trace minimum threshold."""
    request = ChatRequest(messages=[Message(role=r, content=c) for r, c in fixture.messages])
    response = await agent.chat(request)

    recommended_names = {rec.name for rec in response.recommendations}
    recall = recall_at_k(recommended_names, fixture.expected_names)

    logger.info(
        "[%s] Recall@10=%.2f (%d/%d expected, got=%s)",
        fixture.name,
        recall,
        len(recommended_names & fixture.expected_names),
        len(fixture.expected_names),
        sorted(recommended_names),
    )

    assert recall >= fixture.min_recall, (
        f"[{fixture.name}] Recall@10={recall:.2f} below threshold {fixture.min_recall:.2f}. "
        f"Expected={sorted(fixture.expected_names)}, Got={sorted(recommended_names)}"
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fixture",
    CONVERSATION_FIXTURES,
    ids=[f.name for f in CONVERSATION_FIXTURES],
)
async def test_regression_test_type_from_catalog(fixture: ConversationFixture, agent: AssessmentAgent, catalog) -> None:
    """test_type for each recommendation must match the catalog's derived value."""
    request = ChatRequest(messages=[Message(role=r, content=c) for r, c in fixture.messages])
    response = await agent.chat(request)

    for rec in response.recommendations:
        product = catalog.get_by_url(rec.url)
        assert product is not None, f"[{fixture.name}] URL not in catalog: {rec.url!r}"
        assert rec.test_type == product.test_type, (
            f"[{fixture.name}] test_type mismatch for {rec.name!r}: "
            f"got {rec.test_type!r}, catalog has {product.test_type!r}"
        )


# ------------------------------------------------------------------ #
# Recall summary helper (run with -s to see full table)               #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_recall_summary(agent: AssessmentAgent) -> None:
    """Print a Recall@10 summary table for all traces (informational, always passes)."""
    rows = []
    for fixture in CONVERSATION_FIXTURES:
        request = ChatRequest(messages=[Message(role=r, content=c) for r, c in fixture.messages])
        response = await agent.chat(request)
        recommended = {rec.name for rec in response.recommendations}
        recall = recall_at_k(recommended, fixture.expected_names)
        rows.append((fixture.name, recall, len(recommended), len(fixture.expected_names)))

    header = f"{'Trace':<35} {'Recall@10':>10} {'Recs':>5} {'Expected':>8}"
    separator = "-" * len(header)
    print(f"\n{separator}\n{header}\n{separator}")
    for name, recall, recs, expected in rows:
        print(f"{name:<35} {recall:>10.2f} {recs:>5} {expected:>8}")
    mean_recall = sum(r for _, r, _, _ in rows) / len(rows) if rows else 0.0
    print(f"{separator}\n{'Mean Recall@10':<35} {mean_recall:>10.2f}")
