from app.catalog import load_catalog
from app.retrieval import CatalogRetriever


def _result_names(query: str, limit: int = 10) -> list[str]:
    retriever = CatalogRetriever(load_catalog())
    return [result.product.name for result in retriever.search(query, limit=limit)]


def test_retrieval_returns_empty_for_blank_query() -> None:
    retriever = CatalogRetriever(load_catalog())

    assert retriever.search("   ") == []


def test_retrieval_handles_non_positive_limit() -> None:
    retriever = CatalogRetriever(load_catalog())

    assert retriever.search("java developer", limit=0) == []


def test_personality_alias_finds_opq32r() -> None:
    names = _result_names("add a personality and behavioral fit assessment")

    assert names[0] == "Occupational Personality Questionnaire OPQ32r"


def test_cognitive_alias_finds_verify_g_plus() -> None:
    names = _result_names("should we add a cognitive reasoning test for a senior engineer")

    assert "SHL Verify Interactive G+" in names[:3]


def test_rust_query_finds_adjacent_catalog_products() -> None:
    names = _result_names("senior Rust engineer for high-performance networking infrastructure")

    assert "Smart Interview Live Coding" in names[:10]
    assert "Linux Programming (General)" in names[:10]
    assert "Networking and Implementation (New)" in names[:10]


def test_sales_reskilling_query_finds_expected_audit_stack() -> None:
    names = _result_names("annual talent audit to re-skill our sales organization")

    expected = {
        "Global Skills Assessment",
        "Global Skills Development Report",
        "Occupational Personality Questionnaire OPQ32r",
        "OPQ MQ Sales Report",
        "Sales Transformation 2.0 - Individual Contributor",
    }

    assert expected.issubset(set(names[:10]))


def test_healthcare_admin_query_finds_hybrid_products() -> None:
    names = _result_names("bilingual healthcare admin staff in South Texas patient records HIPAA Spanish")

    expected = {
        "HIPAA (Security)",
        "Medical Terminology (New)",
        "Microsoft Word 365 - Essentials (New)",
        "Dependability and Safety Instrument (DSI)",
        "Occupational Personality Questionnaire OPQ32r",
    }

    assert expected.issubset(set(names[:10]))


def test_backend_jd_query_finds_core_technical_stack() -> None:
    names = _result_names(
        "Senior Full-Stack Engineer Core Java Spring REST API SQL AWS Docker backend microservice"
    )

    expected = {
        "Core Java (Advanced Level) (New)",
        "Spring (New)",
        "RESTful Web Services (New)",
        "SQL (New)",
        "Amazon Web Services (AWS) Development (New)",
        "Docker (New)",
    }

    assert expected.issubset(set(names[:10]))


def test_retrieval_results_include_explanations() -> None:
    retriever = CatalogRetriever(load_catalog())
    results = retriever.search("graduate situational judgement")

    assert results
    assert results[0].reasons
