"""Normalize product names from extracted scopes, populate the products table,
and link scopes to their canonical products.

Steps:
1. Upsert all canonical products from data/products_catalog.json into the products table.
2. Load all scope product_name values from the DB.
3. Run each through ProductNormalizer.normalize().
4. For matches with confidence >= 0.75: update scopes.product_id FK.
5. For low-confidence matches: log to data/extracted/product_review_queue.json.
6. Print summary.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import UUID

# Ensure repo root is on sys.path so `src` imports work from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

from src.db.models import Product, ProductCategory, Scope
from src.db.session import async_session
from src.enrichment.product_normalizer import ProductNormalizer

CATALOG_PATH = Path(__file__).parent.parent / "data" / "products_catalog.json"
REVIEW_QUEUE_PATH = Path(__file__).parent.parent / "data" / "extracted" / "product_review_queue.json"
CONFIDENCE_THRESHOLD = 0.75

# Map catalog category strings to ProductCategory enum values
_CATEGORY_MAP: dict[str, ProductCategory] = {
    "ceiling_tile": ProductCategory.CEILING_TILE,
    "grid": ProductCategory.GRID,
    "wall_panel": ProductCategory.WALL_PANEL,
    "baffle": ProductCategory.BAFFLE,
    "fabric": ProductCategory.FABRIC,
    "track": ProductCategory.TRACK,
    "diffuser": ProductCategory.DIFFUSER,
    "masking": ProductCategory.MASKING,
    "wood": ProductCategory.WOOD,
    "felt": ProductCategory.FELT,
    "fabric_wall": ProductCategory.WALL_PANEL,  # closest enum
    "wood_ceiling": ProductCategory.WOOD,
    "sound_masking": ProductCategory.MASKING,
    "other": ProductCategory.OTHER,
}


async def upsert_products(catalog: list[dict[str, Any]]) -> dict[str, UUID]:
    """Upsert products from catalog JSON; return mapping canonical_name -> id."""
    canonical_to_id: dict[str, UUID] = {}

    async with async_session() as session:
        for item in catalog:
            canonical_name: str = item["canonical_name"]
            manufacturer: str | None = item.get("manufacturer")

            # Try to find existing row by canonical_name + manufacturer
            stmt = select(Product).where(
                Product.canonical_name == canonical_name,
                Product.manufacturer == manufacturer,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            raw_category = item.get("category", "other")
            category_enum = _CATEGORY_MAP.get(raw_category, ProductCategory.OTHER)

            if existing is None:
                product = Product(
                    canonical_name=canonical_name,
                    manufacturer=manufacturer,
                    category=category_enum,
                    subcategory=item.get("subcategory"),
                    aliases=item.get("aliases", []),
                    notes=item.get("notes"),
                )
                session.add(product)
                await session.flush()  # get the generated id
                canonical_to_id[canonical_name] = product.id
            else:
                # Update mutable fields in case catalog changed
                existing.category = category_enum
                existing.subcategory = item.get("subcategory")
                existing.aliases = item.get("aliases", [])
                existing.notes = item.get("notes")
                canonical_to_id[canonical_name] = existing.id

        await session.commit()

    return canonical_to_id


async def load_scopes() -> list[tuple[UUID, str]]:
    """Return list of (scope_id, product_name) for all scopes with a product_name."""
    async with async_session() as session:
        stmt = select(Scope.id, Scope.product_name).where(
            Scope.product_name.isnot(None),
            Scope.product_name != "",
        )
        result = await session.execute(stmt)
        return [(row.id, row.product_name) for row in result]


async def update_scope_product_ids(matches: list[tuple[UUID, UUID]]) -> int:
    """Bulk-update scopes.product_id for matched scopes. Returns count updated."""
    if not matches:
        return 0

    async with async_session() as session:
        updated = 0
        for scope_id, product_id in matches:
            stmt = update(Scope).where(Scope.id == scope_id).values(product_id=product_id)
            result = await session.execute(stmt)
            updated += result.rowcount
        await session.commit()

    return updated


async def main() -> None:
    # --- Step 1: Load catalog and upsert products ---
    print("Loading product catalog...")
    catalog: list[dict[str, Any]] = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    print(f"  Catalog has {len(catalog)} entries.")

    print("Upserting products into DB...")
    canonical_to_id = await upsert_products(catalog)
    products_seeded = len(canonical_to_id)
    print(f"  {products_seeded} products seeded/updated.")

    # --- Step 2: Load scope product names ---
    print("Loading scopes from DB...")
    scopes = await load_scopes()
    total_scopes = len(scopes)
    print(f"  {total_scopes} scopes with product_name found.")

    if total_scopes == 0:
        print("No scopes to process. Exiting.")
        return

    # --- Step 3 & 4: Normalize and classify ---
    print("Normalizing product names...")
    normalizer = ProductNormalizer()

    matched_updates: list[tuple[UUID, UUID]] = []  # (scope_id, product_id)
    review_queue: list[dict[str, Any]] = []
    unmatched_names: list[str] = []

    for scope_id, raw_name in scopes:
        result = normalizer.normalize(raw_name)

        # Use primary match (or secondary if no primary)
        match = result.primary or result.secondary

        if match is not None and match.score >= CONFIDENCE_THRESHOLD:
            product_id = canonical_to_id.get(match.canonical_name)
            if product_id is not None:
                matched_updates.append((scope_id, product_id))
            else:
                # Canonical name not in our upserted set (shouldn't happen)
                review_queue.append(
                    {
                        "scope_id": str(scope_id),
                        "raw_name": raw_name,
                        "best_match": match.canonical_name,
                        "score": match.score,
                        "reason": "canonical_name missing from DB insert",
                    }
                )
        else:
            # Low confidence or no match
            review_queue.append(
                {
                    "scope_id": str(scope_id),
                    "raw_name": raw_name,
                    "best_match": match.canonical_name if match else None,
                    "best_match_score": match.score if match else None,
                    "matched_alias": match.matched_alias if match else None,
                    "reason": "below_threshold" if match else "no_match",
                }
            )
            unmatched_names.append(raw_name)

    # --- Step 5: Update DB ---
    print(f"Updating {len(matched_updates)} scope product_id FKs in DB...")
    updated = await update_scope_product_ids(matched_updates)
    print(f"  {updated} rows updated.")

    # --- Write review queue ---
    REVIEW_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_QUEUE_PATH.write_text(
        json.dumps(review_queue, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  Review queue written to {REVIEW_QUEUE_PATH} ({len(review_queue)} entries).")

    # --- Step 6: Summary ---
    matched_count = len(matched_updates)
    review_count = len(review_queue)
    match_pct = (matched_count / total_scopes * 100) if total_scopes else 0.0

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Products seeded/updated : {products_seeded}")
    print(f"  Total scopes processed  : {total_scopes}")
    print(f"  Scopes matched (>=0.75) : {matched_count}  ({match_pct:.1f}%)")
    print(f"  Scopes in review queue  : {review_count}")
    print()

    if unmatched_names:
        counter = Counter(unmatched_names)
        top10 = counter.most_common(10)
        print("Top 10 unmatched product names:")
        for i, (name, count) in enumerate(top10, 1):
            print(f"  {i:2d}. [{count:3d}x] {name!r}")
    else:
        print("All scopes were matched!")


if __name__ == "__main__":
    asyncio.run(main())
