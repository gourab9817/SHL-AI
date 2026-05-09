from dataclasses import dataclass

from app.catalog import CatalogProduct


@dataclass(frozen=True)
class RetrievalResult:
    product: CatalogProduct
    score: float
    reasons: tuple[str, ...]
