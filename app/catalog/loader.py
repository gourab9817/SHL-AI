import json
import logging
from collections import OrderedDict
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.catalog.models import CatalogIndex, CatalogProduct

logger = logging.getLogger(__name__)


DEFAULT_CATALOG_PATH = Path("Data/shl_product_catalog.json")

KEY_TO_TEST_TYPE_CODE = {
    "Ability & Aptitude": "A",
    "Assessment Exercises": "E",
    "Biodata & Situational Judgment": "B",
    "Competencies": "C",
    "Development & 360": "D",
    "Personality & Behavior": "P",
    "Knowledge & Skills": "K",
    "Simulations": "S",
}


class CatalogLoadError(RuntimeError):
    """Raised when the SHL catalog cannot be loaded into a safe in-memory index."""


def load_catalog(path: str | Path = DEFAULT_CATALOG_PATH) -> CatalogIndex:
    catalog_path = Path(path)
    logger.info("Loading SHL product catalog from %s", catalog_path)

    if not catalog_path.exists():
        logger.error("Catalog file does not exist: %s", catalog_path)
        raise CatalogLoadError(f"Catalog file does not exist: {catalog_path}")

    raw_text = catalog_path.read_text(encoding="utf-8")
    documents = _decode_concatenated_json_arrays(raw_text)
    raw_items = _flatten_catalog_documents(documents)
    products = _deduplicate_products(raw_items)
    index = CatalogIndex.from_products(products)

    logger.info(
        "Loaded SHL catalog: %s raw rows, %s unique products, %s whitelisted URLs",
        len(raw_items),
        len(index.products),
        len(index.url_whitelist),
    )
    return index


def _decode_concatenated_json_arrays(raw_text: str) -> list[Any]:
    """Decode one or more JSON documents, tolerating raw control characters.

    The provided catalog currently contains repeated JSON arrays concatenated as
    `][` and at least one raw newline inside a string. `strict=False` lets the
    standard decoder accept those control characters while still preserving real
    JSON validation for structure.
    """
    decoder = json.JSONDecoder(strict=False)
    documents: list[Any] = []
    cursor = 0
    text_length = len(raw_text)

    while cursor < text_length:
        while cursor < text_length and raw_text[cursor].isspace():
            cursor += 1
        if cursor >= text_length:
            break

        try:
            document, cursor = decoder.raw_decode(raw_text, cursor)
        except json.JSONDecodeError as exc:
            logger.error("Failed to decode catalog JSON near byte %s: %s", cursor, exc)
            raise CatalogLoadError(f"Invalid catalog JSON near byte {cursor}") from exc

        documents.append(document)

    if not documents:
        logger.error("Catalog file did not contain any JSON documents")
        raise CatalogLoadError("Catalog file did not contain any JSON documents")

    logger.info("Decoded %s catalog JSON document(s)", len(documents))
    return documents


def _flatten_catalog_documents(documents: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for document_index, document in enumerate(documents, start=1):
        if not isinstance(document, list):
            logger.error("Catalog document %s is %s, expected list", document_index, type(document).__name__)
            raise CatalogLoadError(f"Catalog document {document_index} must be a list")

        for item_index, item in enumerate(document, start=1):
            if not isinstance(item, dict):
                logger.warning(
                    "Skipping non-object catalog row at document=%s item=%s",
                    document_index,
                    item_index,
                )
                continue
            rows.append(item)

    if not rows:
        logger.error("Catalog documents did not contain product rows")
        raise CatalogLoadError("Catalog documents did not contain product rows")

    return rows


def _deduplicate_products(raw_items: list[dict[str, Any]]) -> list[CatalogProduct]:
    products_by_entity_id: OrderedDict[str, CatalogProduct] = OrderedDict()
    duplicate_count = 0
    invalid_count = 0

    for row_number, raw_item in enumerate(raw_items, start=1):
        entity_id = _normalize_text(raw_item.get("entity_id"))
        if not entity_id:
            invalid_count += 1
            logger.warning("Skipping catalog row %s because entity_id is missing", row_number)
            continue

        if entity_id in products_by_entity_id:
            duplicate_count += 1
            continue

        try:
            products_by_entity_id[entity_id] = _build_product(raw_item)
        except (TypeError, ValueError, ValidationError) as exc:
            invalid_count += 1
            logger.warning("Skipping invalid catalog row %s with entity_id=%s: %s", row_number, entity_id, exc)

    if not products_by_entity_id:
        logger.error("No valid catalog products remained after normalization")
        raise CatalogLoadError("No valid catalog products remained after normalization")

    if duplicate_count:
        logger.info("Deduplicated %s repeated catalog row(s)", duplicate_count)
    if invalid_count:
        logger.warning("Skipped %s invalid catalog row(s)", invalid_count)

    return list(products_by_entity_id.values())


def _build_product(raw_item: dict[str, Any]) -> CatalogProduct:
    keys = tuple(_normalize_sequence(raw_item.get("keys")))
    return CatalogProduct(
        entity_id=_normalize_required_text(raw_item.get("entity_id"), "entity_id"),
        name=_normalize_required_text(raw_item.get("name"), "name"),
        url=_normalize_required_text(raw_item.get("link"), "link"),
        description=_normalize_text(raw_item.get("description")),
        keys=keys,
        job_levels=tuple(_normalize_sequence(raw_item.get("job_levels"))),
        languages=tuple(_normalize_sequence(raw_item.get("languages"))),
        duration=_normalize_text(raw_item.get("duration")),
        status=_normalize_text(raw_item.get("status")),
        remote=_normalize_text(raw_item.get("remote")),
        adaptive=_normalize_text(raw_item.get("adaptive")),
        test_type=_derive_test_type(keys),
    )


def _derive_test_type(keys: tuple[str, ...]) -> str:
    if "Development & 360" in keys:
        return KEY_TO_TEST_TYPE_CODE["Development & 360"]

    codes: list[str] = []
    for key in keys:
        code = KEY_TO_TEST_TYPE_CODE.get(key)
        if code and code not in codes:
            codes.append(code)

    return ",".join(codes) if codes else "U"


def _normalize_required_text(value: Any, field_name: str) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return " ".join(value.split())


def _normalize_sequence(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        logger.warning("Expected list in catalog row but got %s; coercing to text", type(value).__name__)
        return [_normalize_text(value)] if _normalize_text(value) else []

    normalized_values: list[str] = []
    for item in value:
        normalized = _normalize_text(item)
        if normalized:
            normalized_values.append(normalized)
    return normalized_values
