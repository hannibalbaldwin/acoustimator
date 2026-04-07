"""Reclassify AP and Other scopes into correct canonical scope types.

Rules derived from analysis of scope_type, tag, product_name, and notes fields.

Canonical scope types: ACT, AWP, FW, SM, WW, RPG, Baffles
(AP and Other are non-canonical and should be eliminated)

Run with:
    uv run python scripts/reclassify_scopes.py
"""

from __future__ import annotations

import asyncio
from collections import Counter
from uuid import UUID

from sqlalchemy import text

from src.db.session import async_session

# ---------------------------------------------------------------------------
# Classification rules
# Each entry is (scope_id, new_scope_type, reason)
# ---------------------------------------------------------------------------

RECLASSIFICATIONS: dict[str, tuple[str, str]] = {
    # -----------------------------------------------------------------------
    # AP → FW  (Fabric Wall — Snap-Tex track system)
    # Notes mention fabric yardage, track linear footage, wall installations
    # -----------------------------------------------------------------------
    "72e9b8e4-73f7-45b9-bb6d-206b9f602ed5": (
        "FW",
        "AP3: fabric yds + track LF formula, wall installs on Floors 3-8",
    ),
    "e199e60d-c336-4327-a51d-d38bd00cdb53": (
        "FW",
        "AP2: fabric yds + track LF formula, 14 walls across floors",
    ),
    "9f760b10-c6c7-4f41-91ca-3cef6cf21c73": (
        "FW",
        "AP4: fabric yds + track LF formula, 8 walls across floors",
    ),
    "e3d1e786-09d9-4ed6-963b-2de43ba6f4b0": ("FW", "AP1: 4 walls Floor 3, fabric + track pattern"),
    "c808386d-a366-44dc-99ea-6ee0e4981656": (
        "FW",
        "Wolf Gordon Gather (Fabric Wall Panels): fabric wall panels with track LF",
    ),
    # -----------------------------------------------------------------------
    # AP → Baffles  (hanging/ceiling acoustic panels, clouds)
    # -----------------------------------------------------------------------
    "938a61b3-5034-4f0c-b925-bf7b92f1efd5": (
        "Baffles",
        "Acoustic Clouds - 3x4x2 Fabric-Wrapped Panels: ceiling clouds",
    ),
    "04e906c1-340f-42a4-b603-fae7988278c0": (
        "Baffles",
        "4x6 Ceiling Panels: ceiling-mounted option",
    ),
    "9d022d30-874d-4fad-9b6d-e5363c2caa1a": (
        "Baffles",
        "Ceiling Mounted Panels (3x4): hanging/ceiling-mounted",
    ),
    "a5d2af89-cf4e-453a-8a28-5dc871ac7974": (
        "Baffles",
        "Option - Additional Panels (21 White on Ceiling, 6 Silver on Wall): ceiling-dominant",
    ),
    "01b0fb83-6925-4f28-b1fb-647a01565c03": (
        "Baffles",
        "3Form Hush Screen SolaPanels (AP02): part of AP/CL group — screen/cloud type",
    ),
    "f3fb8c1a-90e2-4013-8e9e-c4aaf3fb76eb": (
        "Baffles",
        "Rockfon Island - hanging acoustic island panels",
    ),
    "1a2dcc25-1291-4c0e-8149-e998f360d718": (
        "Baffles",
        "Wall Panels and Ceiling Clouds: ceiling cloud component dominant",
    ),
    # -----------------------------------------------------------------------
    # AP → AWP  (Acoustic Wall Panels — fabric-wrapped flat panels on walls)
    # -----------------------------------------------------------------------
    "61d5eb12-0ef1-411a-87f1-b776397702ef": (
        "AWP",
        "2in AVL Acoustech Silver Papier: custom-size fabric-wrapped wall panels",
    ),
    "0fcc7f81-059a-4a11-b6a5-fedb12668986": (
        "AWP",
        "4x6x2in Panels: standard fabric-wrapped wall panels",
    ),
    "e12a6f08-451b-4a12-8195-23f5420d62bf": (
        "AWP",
        "4x8x2in Acoustic Panels: standard wall panels unit-priced",
    ),
    "7079b1d5-4c30-4be5-a2a9-8805847cb826": (
        "AWP",
        "4x8x2in Acoustic Panels: 26 wall panels unit-priced",
    ),
    "63307ad6-17a9-40da-83ba-5db0c6d81ff9": (
        "AWP",
        "4x8x2in Acoustic Panels: 34 wall panels alternate bid",
    ),
    "d6cad187-f2f0-4831-a13c-0159ad5baefb": ("AWP", "4x8x2in Acoustic Panels: 34 panels SF-based"),
    "9135359d-2cf3-48e9-b6c2-fa3ad3bda831": ("AWP", "Acoufelt AT1: felt wall panels"),
    "f816fdd0-63d5-4b34-8968-d821aa41e8c3": ("AWP", "Acoufelt AT3: felt wall panels"),
    "1d4fe408-0730-425b-8082-e320a67970b0": ("AWP", "Acoufelt AT2: felt wall panels"),
    "8bff1eef-6f8e-480c-8b57-9036d23ac565": (
        "AWP",
        "Acoustic Panels: mixed size fabric-wrapped wall panels",
    ),
    "7e93017a-af78-492b-95ff-dc2079310019": ("AWP", "Acoustic Panels: 4x8/4x6/4x4 wall panels"),
    "9ed0c87a-5d09-4df3-9da1-5e60c62eb2d5": ("AWP", "Acoustic Panels: gym wall panels, tax-exempt"),
    "60012da6-14cb-4e02-9a27-1b8e6ed9ec96": (
        "AWP",
        "Acoustic Panels: Silver Neutral custom-size wall panels",
    ),
    "ec5db7e7-721d-4f22-8bee-a1b1e93ebbe3": (
        "AWP",
        "Acoustic Panels (Wrapped/Custom Sizes): mixed wrapped/unwrapped wall panels",
    ),
    "dd7d0886-a44e-4a7c-8d75-b342d1a61f4e": (
        "AWP",
        "Acoustic Panels - Band Room: wall panels all dark blue",
    ),
    "e7b91092-0504-48c5-9747-c27fe88f49b1": (
        "AWP",
        "Acoustic Panels - Sanctuary: wall panels symmetrically installed",
    ),
    "7c63fea3-d6ae-4f5c-8186-ab720a8bc97e": (
        "AWP",
        "Acoustic Panels - Youth Room (Ceiling & Wall): primarily wall panels",
    ),
    "c0cef1f6-eb59-4fe9-a4aa-866c2064f36c": ("AWP", "Acoustic Panels 2x5x2in: 90 wall panels"),
    "ba4bd0d6-80ca-4124-859e-214f0390cc1c": (
        "AWP",
        "Acoustic Panels — Silver Papier and Blue Neutral: fabric-wrapped wall panels",
    ),
    "30e5143c-a39c-467c-99a4-eb1faf21aced": ("AWP", "AkuPanel: wall panels for recording rooms"),
    "6ef61ace-0cdd-4bf6-8dd5-6ce3815e754f": (
        "AWP",
        "AkuPanels 2x8: multi-floor wall panel installation",
    ),
    "651705ab-d17b-441a-aede-147ba21c881c": ("AWP", "Auditorium: wall panels in auditorium"),
    "170a7480-c533-490e-9256-36091bd9d133": ("AWP", "Concord: room wall panels"),
    "6efc77de-24d4-4ff6-be95-0c4058a956f6": ("AWP", "Felt Panels: felt wall panels"),
    "7b1c09c9-6770-413c-88a3-bac2d618d558": (
        "Baffles",
        "FilzFelt AroPlank 1.5 (AP01): part of AP/CL group — plank/baffle system",
    ),  # override above
    "55a410c4-9cff-447b-b7c2-c4e400b7a868": ("AWP", "Lexington: wall panels (44x 4x8 + 12x 4x4)"),
    "ddff58bf-e9d2-4771-aabc-b26cf86025c7": ("AWP", "PSI Panels: vendor-quoted wall panels"),
    "14b5deb4-aa31-4b29-9285-b5a8c9043f41": (
        "AWP",
        "Pinta Willtec Flat Sheets 2in (AP03): flat acoustic sheets, wall treatment",
    ),
    "ff80f251-e427-48c7-9724-77a399a75433": ("AWP", "Tuscany: wall panels (4x4/4x6/2x4)"),
    "d8cee111-c5eb-482b-987e-7fe2a989a426": (
        "AWP",
        "null name: 10x 4x8 + 20x 2x4 panels, wall panels",
    ),
    # -----------------------------------------------------------------------
    # Other → ACT  (Acoustical Ceiling Tile and related ceiling systems)
    # -----------------------------------------------------------------------
    "b7416da7-1966-4f13-9ef6-b6ddab50102a": (
        "ACT",
        "2x2 ASI Microperf Layin: lay-in acoustical ceiling tile",
    ),
    "7808fa3c-0d08-41f8-a458-dd27339c4052": (
        "ACT",
        "Axiom 12in Black: Axiom trim/edge molding for ACT ceiling",
    ),
    "689921dd-5594-453d-91ca-a883544c2e9c": (
        "ACT",
        "Axiom 2in White: Axiom trim/edge molding for ACT ceiling",
    ),
    "b538e3ce-ae6e-4b98-afc5-475ffaaed236": (
        "ACT",
        "MBI Spectrum Perforated PVC Panels: STEAM ceiling lay-in panels",
    ),
    "d031d65f-a9cb-45bc-ba65-fb81757e846f": (
        "ACT",
        "MetalWorks Linear / Axiom Vector Metal Ceiling: metal ceiling panel system",
    ),
    "b30d47a6-4fa5-4942-bfce-2eaf08acd220": (
        "ACT",
        "Tin Ceilings - English Lambs Tongue: decorative ceiling tile",
    ),
    "4e44eda6-6d8c-4178-a179-a77650299fc8": (
        "ACT",
        "Tin Copper Tuscan Bronze Pattern 24: decorative ceiling tile",
    ),
    "be7fbf6e-fe21-4634-9fd1-027372629d08": (
        "ACT",
        "Soniguard above ceiling tile: acoustical ceiling enhancement",
    ),
    # -----------------------------------------------------------------------
    # Other → AWP  (Acoustic Wall Panels)
    # -----------------------------------------------------------------------
    "1bd18918-4910-4c7e-9c44-a04103b2035a": (
        "AWP",
        "Kirei Sunshine (tag CL6/AWP1): wall panel product (AWP tag)",
    ),
    # -----------------------------------------------------------------------
    # Other → Baffles  (hanging/ceiling clouds, baffles, blades)
    # -----------------------------------------------------------------------
    "4e2f262c-fa9c-4b5a-ba60-8ea5958dd6f7": ("Baffles", "CSI Clouds: acoustic clouds"),
    "f041f192-5db5-424f-b7d5-401edb87a87f": ("Baffles", "J2 Clouds: acoustic cloud panels"),
    "ca0d87ae-7bfb-47fc-97f6-967c403e62e8": (
        "Baffles",
        "Zintra Blanchard Clouds: 8 acoustic clouds",
    ),
    "faf8a2e3-98bf-418c-8d9c-6fe1a23a068e": (
        "Baffles",
        "Feltworks Blades: 48 hanging felt blade baffles",
    ),
    "6dd9aaf5-3860-4126-9559-1dd092a939da": (
        "Baffles",
        "Soundply Cloud LRM51 Lino Plank Walnut: acoustic cloud ceiling",
    ),
    "ab37a9b5-c1f5-4f1f-869a-0c7ce782634d": (
        "Baffles",
        "Banners: 54 acoustic hanging banners (MBI)",
    ),
    "1e91a438-5902-4be2-a284-31e1486154bf": ("Baffles", "Reflectors: 22 acoustic reflectors (AVL)"),
    # -----------------------------------------------------------------------
    # Other → RPG  (Specialty acoustic diffusers/reflectors)
    # -----------------------------------------------------------------------
    "cb8aadc9-88fe-4cba-9902-461f7f2b03d9": (
        "RPG",
        "Convex/Concave #5441 & 5442: notes explicitly say RPG-type diffuser",
    ),
    "1539dc81-5f47-4761-b250-3287b19c1a6b": (
        "RPG",
        "Remount 4 Cloud Diffusers: diffuser remount service",
    ),
    # -----------------------------------------------------------------------
    # Other → SM  (Sound Masking / speaker systems)
    # -----------------------------------------------------------------------
    "3b9a0174-bef0-4eb7-a74a-19ad5bcae58b": ("SM", "123 Speakers: speaker installation labor"),
    "3118ac1d-6d6e-40d6-8169-a9222c199845": ("SM", "Classic Speakers: 30 speakers at $190 each"),
    # -----------------------------------------------------------------------
    # Other → FW  (Fabric Wall)
    # Tags 105A/105D: SF + Yds pricing pattern = FW (fabric + yardage = Snap-Tex)
    # -----------------------------------------------------------------------
    "19737eea-e96a-4944-8048-898d9d84335a": (
        "FW",
        "105A: SF at $1.55 + Yds at $21.00 — fabric wall pricing pattern",
    ),
    "054575d5-c9cc-4e9f-8c82-d1397f19c830": (
        "FW",
        "105D: SF at $1.55 + Yds at $21.00 — fabric wall pricing pattern",
    ),
    # -----------------------------------------------------------------------
    # Other → Other  (keep as-is — truly ambiguous or non-acoustic materials)
    # R-19 Insulation, Pipe Grid, Unistrut, null-name ambiguous scopes stay Other
    # -----------------------------------------------------------------------
    # "f94ec38e": Other  (R-19 Insulation — construction material)
    # "f9e06f19": Other  (Pipe Grid System — structural support)
    # "b7996623": Other  (Unistrut — structural hardware)
    # "dc809571": Other  (null name, 20 units @ $247)
    # "b48c807b": Other  (null name, vendor quote-based)
    # "cd8ed6ec": Other  (null name, cost revision notes only)
}


async def main() -> None:
    async with async_session() as session:
        # ------------------------------------------------------------------
        # 1. Snapshot before counts
        # ------------------------------------------------------------------
        before_rows = await session.execute(
            text("SELECT scope_type, COUNT(*) as cnt FROM scopes GROUP BY scope_type ORDER BY cnt DESC")
        )
        before_counts = {r.scope_type: r.cnt for r in before_rows}

        print("=" * 60)
        print("BEFORE reclassification:")
        for stype, cnt in sorted(before_counts.items(), key=lambda x: -x[1]):
            print(f"  {stype:10s}: {cnt}")
        print(f"  {'TOTAL':10s}: {sum(before_counts.values())}")
        print()

        # ------------------------------------------------------------------
        # 2. Apply reclassifications
        # ------------------------------------------------------------------
        change_counts: Counter[str] = Counter()
        per_type: dict[str, list[str]] = {}

        for scope_id_str, (new_type, reason) in RECLASSIFICATIONS.items():
            scope_id = UUID(scope_id_str)
            result = await session.execute(
                text(
                    "UPDATE scopes SET scope_type = :new_type "
                    "WHERE id = :scope_id AND scope_type != :new_type "
                    "RETURNING id, scope_type"
                ),
                {"new_type": new_type, "scope_id": scope_id},
            )
            updated = result.fetchall()
            if updated:
                change_counts[new_type] += 1
                per_type.setdefault(new_type, []).append(reason)

        await session.commit()
        print(f"Updated {sum(change_counts.values())} scopes total.")
        print()
        print("Changes by new scope_type:")
        for stype, cnt in sorted(change_counts.items(), key=lambda x: -x[1]):
            print(f"  → {stype:10s}: {cnt} scopes reclassified")
        print()

        # ------------------------------------------------------------------
        # 3. Snapshot after counts
        # ------------------------------------------------------------------
        after_rows = await session.execute(
            text("SELECT scope_type, COUNT(*) as cnt FROM scopes GROUP BY scope_type ORDER BY cnt DESC")
        )
        after_counts = {r.scope_type: r.cnt for r in after_rows}

        print("=" * 60)
        print("AFTER reclassification:")
        for stype, cnt in sorted(after_counts.items(), key=lambda x: -x[1]):
            print(f"  {stype:10s}: {cnt}")
        print(f"  {'TOTAL':10s}: {sum(after_counts.values())}")
        print()

        # ------------------------------------------------------------------
        # 4. Remaining AP / Other scopes (not reclassified)
        # ------------------------------------------------------------------
        remaining = await session.execute(
            text(
                "SELECT scope_type, id, tag, product_name FROM scopes "
                "WHERE scope_type IN ('AP', 'Other') ORDER BY scope_type, product_name"
            )
        )
        leftover = remaining.fetchall()
        if leftover:
            print(f"Remaining AP/Other scopes not reclassified ({len(leftover)}):")
            for row in leftover:
                print(f"  [{row.scope_type}] id={row.id}  tag={row.tag!r}  name={row.product_name!r}")
        else:
            print("All AP and Other scopes have been reclassified.")


if __name__ == "__main__":
    asyncio.run(main())
