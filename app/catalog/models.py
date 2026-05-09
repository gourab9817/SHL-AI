from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def normalize_lookup_key(value: str) -> str:
    """Normalize catalog names and URLs for stable exact lookup."""
    return " ".join(value.casefold().strip().split())


class CatalogProduct(BaseModel):
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    description: str = ""
    keys: tuple[str, ...] = Field(default_factory=tuple)
    job_levels: tuple[str, ...] = Field(default_factory=tuple)
    languages: tuple[str, ...] = Field(default_factory=tuple)
    duration: str = ""
    status: str = ""
    remote: str = ""
    adaptive: str = ""
    test_type: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("url")
    @classmethod
    def url_must_be_catalog_link(cls, value: str) -> str:
        parsed = HttpUrl(value)
        if parsed.scheme != "https":
            raise ValueError("catalog URL must use https")
        if parsed.host != "www.shl.com":
            raise ValueError("catalog URL must be hosted on www.shl.com")
        if not parsed.path.startswith("/products/product-catalog/view/"):
            raise ValueError("catalog URL must point to an SHL product catalog view")
        return value


class CatalogIndex(BaseModel):
    products: tuple[CatalogProduct, ...]
    by_entity_id: dict[str, CatalogProduct]
    by_name: dict[str, CatalogProduct]
    by_url: dict[str, CatalogProduct]
    url_whitelist: frozenset[str]

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    @classmethod
    def from_products(cls, products: Iterable[CatalogProduct]) -> "CatalogIndex":
        product_tuple = tuple(products)
        by_entity_id = {product.entity_id: product for product in product_tuple}
        by_name = {normalize_lookup_key(product.name): product for product in product_tuple}
        by_url = {product.url: product for product in product_tuple}

        return cls(
            products=product_tuple,
            by_entity_id=by_entity_id,
            by_name=by_name,
            by_url=by_url,
            url_whitelist=frozenset(by_url),
        )

    def get_by_entity_id(self, entity_id: str) -> CatalogProduct | None:
        return self.by_entity_id.get(entity_id)

    def get_by_name(self, name: str) -> CatalogProduct | None:
        return self.by_name.get(normalize_lookup_key(name))

    def get_by_url(self, url: str) -> CatalogProduct | None:
        return self.by_url.get(url)

    def as_recommendation(self, product: CatalogProduct) -> dict[str, Any]:
        return {
            "name": product.name,
            "url": product.url,
            "test_type": product.test_type,
        }
