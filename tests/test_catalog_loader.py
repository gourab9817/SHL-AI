from pathlib import Path

import pytest

from app.catalog import CatalogLoadError, load_catalog


CATALOG_PATH = Path("Data/shl_product_catalog.json")


def test_catalog_loader_deduplicates_local_catalog() -> None:
    catalog = load_catalog(CATALOG_PATH)

    assert len(catalog.products) == 377
    assert len(catalog.by_entity_id) == 377
    assert len(catalog.url_whitelist) == 377


def test_catalog_loader_normalizes_embedded_newlines() -> None:
    catalog = load_catalog(CATALOG_PATH)

    product = catalog.get_by_entity_id("4207")

    assert product is not None
    assert product.name == "Microsoft 365 (New)"


def test_catalog_lookup_finds_known_trace_products() -> None:
    catalog = load_catalog(CATALOG_PATH)

    expected_names = [
        "Occupational Personality Questionnaire OPQ32r",
        "Global Skills Assessment",
        "SHL Verify Interactive G+",
        "Graduate Scenarios",
        "HIPAA (Security)",
        "Core Java (Advanced Level) (New)",
    ]

    for name in expected_names:
        assert catalog.get_by_name(name) is not None


def test_catalog_recommendation_shape_is_derived_from_catalog() -> None:
    catalog = load_catalog(CATALOG_PATH)
    product = catalog.get_by_name("Global Skills Assessment")

    assert product is not None
    assert catalog.as_recommendation(product) == {
        "name": "Global Skills Assessment",
        "url": "https://www.shl.com/products/product-catalog/view/global-skills-assessment/",
        "test_type": "C,K",
    }


def test_catalog_urls_are_whitelisted_shl_product_urls() -> None:
    catalog = load_catalog(CATALOG_PATH)

    assert all(url.startswith("https://www.shl.com/products/product-catalog/view/") for url in catalog.url_whitelist)


def test_catalog_loader_rejects_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.json"

    with pytest.raises(CatalogLoadError):
        load_catalog(missing_file)
