"""Unit tests for ResponseVerifier.

Tests confirm that the verifier enforces catalog integrity and schema rules
without requiring LLM access. Fixtures use a real catalog index so URL
whitelist checks are authoritative.
"""
import pytest

from app.catalog import load_catalog
from app.schemas import ChatResponse, RecommendationItem
from app.verification import ResponseVerifier


# ------------------------------------------------------------------ #
# Shared fixtures                                                      #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def verifier(catalog) -> ResponseVerifier:
    return ResponseVerifier(catalog)


def _good_rec(catalog, name: str) -> RecommendationItem:
    product = catalog.get_by_name(name)
    assert product is not None, f"Product not in catalog: {name!r}"
    return RecommendationItem(name=product.name, url=product.url, test_type=product.test_type)


def _response(recs: list[RecommendationItem], *, end: bool = False) -> ChatResponse:
    return ChatResponse(reply="Here are recommendations.", recommendations=recs, end_of_conversation=end)


# ------------------------------------------------------------------ #
# Intents that must produce empty recommendations                     #
# ------------------------------------------------------------------ #

def test_clarify_strips_any_recommendations(verifier, catalog) -> None:
    rec = _good_rec(catalog, "Occupational Personality Questionnaire OPQ32r")
    result = verifier.verify(_response([rec]), intent="clarify")

    assert result.recommendations == []
    assert result.end_of_conversation is False


def test_refuse_strips_any_recommendations(verifier, catalog) -> None:
    rec = _good_rec(catalog, "SHL Verify Interactive G+")
    result = verifier.verify(_response([rec]), intent="refuse")

    assert result.recommendations == []
    assert result.end_of_conversation is False


def test_compare_strips_any_recommendations(verifier, catalog) -> None:
    rec = _good_rec(catalog, "Graduate Scenarios")
    result = verifier.verify(_response([rec]), intent="compare")

    assert result.recommendations == []
    assert result.end_of_conversation is False


def test_clarify_preserves_reply_text(verifier, catalog) -> None:
    rec = _good_rec(catalog, "Occupational Personality Questionnaire OPQ32r")
    result = verifier.verify(_response([rec]), intent="clarify")

    assert result.reply == "Here are recommendations."


# ------------------------------------------------------------------ #
# URL whitelist enforcement                                            #
# ------------------------------------------------------------------ #

def test_non_whitelisted_url_is_stripped(verifier, catalog) -> None:
    bad_rec = RecommendationItem(
        name="Fake Assessment",
        url="https://www.shl.com/products/product-catalog/view/fake-assessment-xyz/",
        test_type="K",
    )
    good_rec = _good_rec(catalog, "SHL Verify Interactive G+")
    result = verifier.verify(_response([bad_rec, good_rec]), intent="recommend")

    names = {r.name for r in result.recommendations}
    assert "Fake Assessment" not in names
    assert "SHL Verify Interactive G+" in names


def test_all_good_recommendations_preserved(verifier, catalog) -> None:
    recs = [
        _good_rec(catalog, "Occupational Personality Questionnaire OPQ32r"),
        _good_rec(catalog, "SHL Verify Interactive G+"),
        _good_rec(catalog, "Graduate Scenarios"),
    ]
    result = verifier.verify(_response(recs), intent="recommend")

    assert len(result.recommendations) == 3


def test_all_bad_urls_yields_empty_list(verifier) -> None:
    bad_rec = RecommendationItem(
        name="Hallucinated Test",
        url="https://www.shl.com/products/product-catalog/view/does-not-exist-001/",
        test_type="K",
    )
    result = verifier.verify(_response([bad_rec]), intent="recommend")

    assert result.recommendations == []


# ------------------------------------------------------------------ #
# test_type re-derivation from catalog                                #
# ------------------------------------------------------------------ #

def test_test_type_is_re_derived_from_catalog(verifier, catalog) -> None:
    product = catalog.get_by_name("Occupational Personality Questionnaire OPQ32r")
    assert product is not None
    tampered_rec = RecommendationItem(
        name=product.name,
        url=product.url,
        test_type="WRONG_TYPE",
    )
    result = verifier.verify(_response([tampered_rec]), intent="recommend")

    assert len(result.recommendations) == 1
    assert result.recommendations[0].test_type == product.test_type


def test_canonical_name_comes_from_catalog(verifier, catalog) -> None:
    product = catalog.get_by_name("Occupational Personality Questionnaire OPQ32r")
    assert product is not None
    tampered_rec = RecommendationItem(
        name="OPQ32r (renamed by LLM)",
        url=product.url,
        test_type=product.test_type,
    )
    result = verifier.verify(_response([tampered_rec]), intent="recommend")

    assert len(result.recommendations) == 1
    assert result.recommendations[0].name == product.name


# ------------------------------------------------------------------ #
# Recommendation count enforcement                                    #
# ------------------------------------------------------------------ #

def test_more_than_ten_trimmed_to_ten(verifier, catalog) -> None:
    recs = [_good_rec(catalog, p.name) for p in catalog.products[:12]]
    result = verifier.verify(_response(recs), intent="recommend")

    assert len(result.recommendations) <= 10


def test_duplicate_urls_deduplicated(verifier, catalog) -> None:
    rec = _good_rec(catalog, "Occupational Personality Questionnaire OPQ32r")
    result = verifier.verify(_response([rec, rec]), intent="recommend")

    assert len(result.recommendations) == 1


# ------------------------------------------------------------------ #
# end_of_conversation semantics                                       #
# ------------------------------------------------------------------ #

def test_end_of_conversation_preserved_when_recs_valid(verifier, catalog) -> None:
    rec = _good_rec(catalog, "Occupational Personality Questionnaire OPQ32r")
    result = verifier.verify(_response([rec], end=True), intent="finalize")

    assert result.end_of_conversation is True


def test_end_of_conversation_cleared_when_all_recs_stripped(verifier) -> None:
    bad_rec = RecommendationItem(
        name="Gone",
        url="https://www.shl.com/products/product-catalog/view/nonexistent-product-xyz/",
        test_type="K",
    )
    result = verifier.verify(_response([bad_rec], end=True), intent="finalize")

    assert result.end_of_conversation is False
    assert result.recommendations == []


def test_clarify_always_sets_end_of_conversation_false(verifier, catalog) -> None:
    rec = _good_rec(catalog, "Graduate Scenarios")
    result = verifier.verify(_response([rec], end=True), intent="clarify")

    assert result.end_of_conversation is False


# ------------------------------------------------------------------ #
# Empty input edge cases                                              #
# ------------------------------------------------------------------ #

def test_empty_recommendation_list_unchanged(verifier) -> None:
    result = verifier.verify(_response([]), intent="recommend")

    assert result.recommendations == []


def test_empty_recommendation_list_for_finalize_clears_end(verifier) -> None:
    result = verifier.verify(_response([], end=True), intent="finalize")

    assert result.end_of_conversation is False
