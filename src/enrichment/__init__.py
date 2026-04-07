"""Enrichment module: product name normalization and catalog lookups."""

from .product_normalizer import (
    NormalizationResult,
    ProductMatch,
    ProductNormalizer,
    normalize_product_name,
)

__all__ = [
    "NormalizationResult",
    "ProductMatch",
    "ProductNormalizer",
    "normalize_product_name",
]
