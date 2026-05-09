"""Unit tests for LLMGenerator.

The GroqClient is mocked throughout — these tests verify:
- Name resolution against the catalog
- Safety-net removal enforcement after LLM selection
- Deterministic fallback on LLM unavailability, None return, or empty plans
- Clarify and compare reply delegation and fallback
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.responder import DeterministicResponder
from app.catalog import load_catalog
from app.conversation import ConversationContextExtractor
from app.llm.generator import LLMGenerator
from app.schemas import Message


# ------------------------------------------------------------------ #
# Shared fixtures                                                      #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def extractor(catalog):
    return ConversationContextExtractor(catalog)


@pytest.fixture()
def responder():
    return DeterministicResponder()


def _make_available_client(*, json_result=None, text_result=None) -> MagicMock:
    client = MagicMock()
    client.is_available = True
    client.complete_json = AsyncMock(return_value=json_result)
    client.complete = AsyncMock(return_value=text_result)
    return client


def _make_unavailable_client() -> MagicMock:
    client = MagicMock()
    client.is_available = False
    return client


def _context(extractor, messages):
    return extractor.extract([Message(role=r, content=c) for r, c in messages])


# ------------------------------------------------------------------ #
# select_shortlist_with_reply                                          #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_select_shortlist_resolves_valid_names(catalog, extractor, responder) -> None:
    llm_payload = {
        "selected_names": ["Occupational Personality Questionnaire OPQ32r"],
        "reply": "OPQ32r is ideal for senior roles.",
    }
    client = _make_available_client(json_result=llm_payload)
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "Senior manager role")])

    products, reply = await generator.select_shortlist_with_reply(context, [], "recommend")

    assert len(products) == 1
    assert products[0].name == "Occupational Personality Questionnaire OPQ32r"
    assert reply == "OPQ32r is ideal for senior roles."


@pytest.mark.anyio
async def test_select_shortlist_drops_unresolvable_names(catalog, extractor, responder) -> None:
    llm_payload = {
        "selected_names": ["Completely Fake Assessment XYZ"],
        "reply": "Good fit.",
    }
    client = _make_available_client(json_result=llm_payload)
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "Backend engineer")])

    products, reply = await generator.select_shortlist_with_reply(context, [], "recommend")

    assert products == []
    assert reply == ""


@pytest.mark.anyio
async def test_select_shortlist_returns_empty_when_llm_unavailable(catalog, extractor, responder) -> None:
    client = _make_unavailable_client()
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "Data analyst role")])

    products, reply = await generator.select_shortlist_with_reply(context, [], "recommend")

    assert products == []
    assert reply == ""


@pytest.mark.anyio
async def test_select_shortlist_returns_empty_when_llm_returns_none(catalog, extractor, responder) -> None:
    client = _make_available_client(json_result=None)
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "Nurse hiring")])

    products, reply = await generator.select_shortlist_with_reply(context, [], "recommend")

    assert products == []
    assert reply == ""


@pytest.mark.anyio
async def test_select_shortlist_enforces_removal_safety_net(catalog, extractor, responder) -> None:
    llm_payload = {
        "selected_names": [
            "Occupational Personality Questionnaire OPQ32r",
            "SHL Verify Interactive G+",
        ],
        "reply": "These two cover personality and cognitive.",
    }
    client = _make_available_client(json_result=llm_payload)
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)

    context = _context(
        extractor,
        [
            ("user", "Leadership hiring"),
            ("assistant", "I recommend OPQ32r and Verify G+."),
            ("user", "Drop the OPQ"),
        ],
    )

    products, _ = await generator.select_shortlist_with_reply(context, [], "refine")

    names = {p.name for p in products}
    assert "Occupational Personality Questionnaire OPQ32r" not in names
    assert "SHL Verify Interactive G+" in names


@pytest.mark.anyio
async def test_select_shortlist_deduplicates_products(catalog, extractor, responder) -> None:
    llm_payload = {
        "selected_names": [
            "Occupational Personality Questionnaire OPQ32r",
            "Occupational Personality Questionnaire OPQ32r",
        ],
        "reply": "Repeated by the model.",
    }
    client = _make_available_client(json_result=llm_payload)
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "Senior manager")])

    products, _ = await generator.select_shortlist_with_reply(context, [], "recommend")

    assert len(products) == 1


# ------------------------------------------------------------------ #
# generate_clarify_reply                                               #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_generate_clarify_reply_returns_llm_text(catalog, extractor, responder) -> None:
    client = _make_available_client(text_result="What seniority level is this role?")
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "I need an assessment")])

    reply = await generator.generate_clarify_reply(context)

    assert reply == "What seniority level is this role?"


@pytest.mark.anyio
async def test_generate_clarify_reply_falls_back_when_llm_unavailable(catalog, extractor, responder) -> None:
    client = _make_unavailable_client()
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "I need an assessment")])

    reply = await generator.generate_clarify_reply(context)

    assert len(reply) > 0
    assert "?" in reply


@pytest.mark.anyio
async def test_generate_clarify_reply_falls_back_when_llm_returns_empty(catalog, extractor, responder) -> None:
    client = _make_available_client(text_result="")
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "I need an assessment")])

    reply = await generator.generate_clarify_reply(context)

    assert len(reply) > 0


# ------------------------------------------------------------------ #
# generate_compare_reply                                               #
# ------------------------------------------------------------------ #

@pytest.mark.anyio
async def test_generate_compare_reply_returns_llm_text(catalog, extractor, responder) -> None:
    client = _make_available_client(
        text_result="OPQ32r measures personality; Verify G+ measures cognitive ability."
    )
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(
        extractor,
        [("user", "Compare OPQ32r and Verify G+")],
    )
    products = tuple(p for p in catalog.products[:2])

    reply = await generator.generate_compare_reply(context, products)

    assert "OPQ32r" in reply or "personality" in reply


@pytest.mark.anyio
async def test_generate_compare_reply_falls_back_when_llm_unavailable(catalog, extractor, responder) -> None:
    client = _make_unavailable_client()
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "Compare two assessments")])
    products = tuple(p for p in catalog.products[:2])

    reply = await generator.generate_compare_reply(context, products)

    assert len(reply) > 0


@pytest.mark.anyio
async def test_generate_compare_reply_falls_back_for_single_product(catalog, extractor, responder) -> None:
    client = _make_available_client(text_result="Great product.")
    generator = LLMGenerator(client=client, catalog=catalog, responder=responder)
    context = _context(extractor, [("user", "Compare one")])
    single_product = (catalog.products[0],)

    reply = await generator.generate_compare_reply(context, single_product)

    assert "Which SHL assessments" in reply
