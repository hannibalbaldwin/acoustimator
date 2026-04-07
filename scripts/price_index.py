"""
Phase 2.3: Historical Price Indexing
=====================================
Analyzes historical cost/SF trends by scope type, applies labor rate normalization,
and produces a price index report saved to data/extracted/price_index.json.

Key findings from data audit:
- All quote_date fields are NULL in DB (extraction did not populate them)
- Dates from JSON source files are sparse and inconsistently formatted (12/127 files)
- Labor rate (daily_labor_rate) is the primary temporal proxy: older projects use
  lower rates ($486-$504), newer ones use $522-$580, latest use $725/day
- Analysis proceeds without time-series grouping; uses labor rate as era proxy
"""

import asyncio
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

# Ensure project root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from src.db.session import async_session  # noqa: E402

# ---------------------------------------------------------------------------
# Constants from ANALYSIS.md
# ---------------------------------------------------------------------------

CURRENT_LABOR_RATE = 725.0  # $/day — current target rate for normalization

# Labor rate era mapping — ascending order maps to approximate time periods
LABOR_RATE_ERAS: list[tuple[float, float, str]] = [
    (0, 490, "Era 1 (~pre-2023, $486/day)"),
    (490, 514, "Era 2 (2023-early 2024, $504/day)"),
    (514, 535, "Era 3 (early-mid 2024, $522/day)"),
    (535, 556, "Era 4 (mid 2024, $540/day)"),
    (556, 580, "Era 5 (late 2024, $558/day)"),
    (580, 700, "Era 6 (2025, $580-$650/day)"),
    (700, 9999, "Era 7 (current, $725/day)"),
]

# ANALYSIS.md benchmarks: expected cost/SF ranges per scope type
BENCHMARKS: dict[str, dict] = {
    "ACT": {"min": 1.57, "max": 9.44, "typical_markup_min": 0.15, "typical_markup_max": 0.45},
    "AWP": {"min": 21.0, "max": 34.0, "typical_markup_min": 0.20, "typical_markup_max": 0.40},
    "AP": {"min": 5.0, "max": 35.0, "typical_markup_min": 0.25, "typical_markup_max": 0.75},
    "Baffles": {"min": 10.0, "max": 150.0, "typical_markup_min": 0.25, "typical_markup_max": 0.50},
    "FW": {"min": 3.0, "max": 15.0, "typical_markup_min": 0.30, "typical_markup_max": 0.50},
    "SM": {"min": 1.0, "max": 20.0, "typical_markup_min": 0.40, "typical_markup_max": 0.75},
    "WW": {"min": 14.0, "max": 45.0, "typical_markup_min": 0.15, "typical_markup_max": 0.35},
    "RPG": {"min": 5.0, "max": 100.0, "typical_markup_min": 0.30, "typical_markup_max": 0.50},
    "Other": {"min": 0.5, "max": 200.0, "typical_markup_min": 0.10, "typical_markup_max": 1.00},
}

SCOPE_TYPE_ORDER = ["ACT", "AWP", "AP", "Baffles", "FW", "WW", "SM", "RPG", "Other"]


def _era_for_rate(rate: float) -> str:
    for lo, hi, label in LABOR_RATE_ERAS:
        if lo <= rate < hi:
            return label
    return "Era Unknown"


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "median": None, "std": None, "min": None, "max": None}
    n = len(values)
    mean = statistics.mean(values)
    median = statistics.median(values)
    std = statistics.stdev(values) if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mean, 4),
        "median": round(median, 4),
        "std": round(std, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def normalize_labor_cost(
    labor_price: float | None,
    daily_rate: float | None,
    man_days: float | None,
    target_rate: float = CURRENT_LABOR_RATE,
) -> float | None:
    """Return labor cost normalized to target_rate/day.

    Prefer man_days * target_rate when man_days is available.
    Fall back to scaling labor_price by rate ratio when only price is known.
    """
    if man_days is not None and man_days > 0:
        return round(man_days * target_rate, 2)
    if labor_price is not None and daily_rate is not None and daily_rate > 0:
        return round(labor_price * (target_rate / daily_rate), 2)
    return None


def flag_outliers(cost: float, scope_type: str) -> list[str]:
    """Return list of outlier flags for a given cost/unit value."""
    flags: list[str] = []
    bench = BENCHMARKS.get(scope_type)
    if not bench:
        return flags
    if cost < bench["min"] * 0.5:
        flags.append(f"VERY_LOW (<50% of benchmark min {bench['min']})")
    elif cost < bench["min"]:
        flags.append(f"LOW (<benchmark min {bench['min']})")
    if cost > bench["max"] * 2.0:
        flags.append(f"VERY_HIGH (>200% of benchmark max {bench['max']})")
    elif cost > bench["max"]:
        flags.append(f"HIGH (>benchmark max {bench['max']})")
    return flags


async def fetch_scopes() -> list[dict]:
    """Pull all scopes from DB with project date and cost data."""
    async with async_session() as s:
        rows = await s.execute(
            text("""
                SELECT
                    s.id::text            AS scope_id,
                    s.scope_type,
                    s.cost_per_unit,
                    s.markup_pct,
                    s.man_days,
                    s.square_footage,
                    s.daily_labor_rate,
                    s.labor_price,
                    s.material_cost,
                    s.material_price,
                    s.total,
                    s.product_name,
                    s.tag,
                    p.quote_number,
                    p.quote_date,
                    p.name             AS project_name,
                    p.id::text         AS project_id
                FROM scopes s
                JOIN projects p ON s.project_id = p.id
                WHERE s.scope_type IS NOT NULL
                ORDER BY s.scope_type, p.quote_number NULLS LAST
            """)
        )
        return [dict(r._mapping) for r in rows]


def analyze(scopes: list[dict]) -> dict:
    """
    Build the full price index analysis structure.

    Returns a dict with:
    - metadata
    - date_coverage (sparse — documented)
    - per_scope_type stats
    - labor_rate_distribution
    - labor_normalized_analysis
    - era_analysis (grouping by labor rate era as temporal proxy)
    - outliers
    """
    total = len(scopes)
    with_date = sum(1 for s in scopes if s.get("quote_date"))
    with_cost = sum(1 for s in scopes if s.get("cost_per_unit") is not None)
    with_man_days = sum(1 for s in scopes if s.get("man_days") is not None)
    with_labor_rate = sum(1 for s in scopes if s.get("daily_labor_rate") is not None)

    # --- 1. Per-scope-type raw stats ---
    by_type: dict[str, list[dict]] = defaultdict(list)
    for s in scopes:
        by_type[s["scope_type"]].append(s)

    per_type_stats: dict[str, dict] = {}
    for stype in SCOPE_TYPE_ORDER:
        rows = by_type.get(stype, [])
        costs = [float(r["cost_per_unit"]) for r in rows if r.get("cost_per_unit") is not None]
        markups = [float(r["markup_pct"]) * 100 for r in rows if r.get("markup_pct") is not None]
        man_days_list = [float(r["man_days"]) for r in rows if r.get("man_days") is not None]
        sf_list = [float(r["square_footage"]) for r in rows if r.get("square_footage") is not None]
        rates = [float(r["daily_labor_rate"]) for r in rows if r.get("daily_labor_rate") is not None]

        # Derived: man_days per 1000 SF productivity ratio
        prod_ratios: list[float] = []
        for r in rows:
            md = _safe_float(r.get("man_days"))
            sf = _safe_float(r.get("square_footage"))
            if md and sf and sf > 0:
                prod_ratios.append(md / sf * 1000)  # man-days per 1000 SF

        # Outlier detection
        outlier_rows: list[dict] = []
        for r in rows:
            c = _safe_float(r.get("cost_per_unit"))
            if c is None:
                continue
            flags = flag_outliers(c, stype)
            if flags:
                outlier_rows.append(
                    {
                        "project": r["project_name"],
                        "tag": r.get("tag"),
                        "product": r.get("product_name"),
                        "cost_per_unit": c,
                        "flags": flags,
                    }
                )

        per_type_stats[stype] = {
            "total_scopes": len(rows),
            "cost_per_unit": _stats(costs),
            "markup_pct": _stats(markups),
            "man_days": _stats(man_days_list),
            "square_footage": _stats(sf_list),
            "daily_labor_rate": _stats(rates),
            "man_days_per_1000sf": _stats(prod_ratios),
            "benchmark": BENCHMARKS.get(stype, {}),
            "outlier_count": len(outlier_rows),
            "outliers": outlier_rows,
        }

    # --- 2. Labor rate distribution across all scopes ---
    all_rates = [float(s["daily_labor_rate"]) for s in scopes if s.get("daily_labor_rate")]
    rate_buckets: dict[str, int] = defaultdict(int)
    for r in all_rates:
        bucket = _era_for_rate(r)
        rate_buckets[bucket] += 1

    # --- 3. Era-grouped analysis (labor rate as temporal proxy) ---
    era_groups: dict[str, list[dict]] = defaultdict(list)
    for s in scopes:
        rate = _safe_float(s.get("daily_labor_rate"))
        if rate:
            era = _era_for_rate(rate)
            era_groups[era].append(s)

    era_analysis: dict[str, dict] = {}
    for _era_label, _, era_name in LABOR_RATE_ERAS:
        rows = era_groups.get(era_name, [])
        costs = [float(r["cost_per_unit"]) for r in rows if r.get("cost_per_unit")]
        # By scope type within era
        by_stype_in_era: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            c = _safe_float(r.get("cost_per_unit"))
            if c:
                by_stype_in_era[r["scope_type"]].append(c)

        era_analysis[era_name] = {
            "scope_count": len(rows),
            "overall_cost_per_unit": _stats(costs),
            "by_scope_type": {st: _stats(vals) for st, vals in by_stype_in_era.items()},
        }

    # --- 4. Labor normalization analysis ---
    normalized_records: list[dict] = []
    for s in scopes:
        lp = _safe_float(s.get("labor_price"))
        rate = _safe_float(s.get("daily_labor_rate"))
        md = _safe_float(s.get("man_days"))
        sf = _safe_float(s.get("square_footage"))
        _safe_float(s.get("material_price"))

        norm_labor = normalize_labor_cost(lp, rate, md, CURRENT_LABOR_RATE)
        if norm_labor is None or sf is None or sf == 0:
            continue

        _safe_float(s.get("total"))
        orig_labor_per_sf = (lp / sf) if (lp and sf) else None
        norm_labor_per_sf = norm_labor / sf if sf > 0 else None
        labor_adjustment_factor = (norm_labor / lp) if (lp and lp > 0) else None

        normalized_records.append(
            {
                "scope_id": s["scope_id"],
                "project": s["project_name"],
                "scope_type": s["scope_type"],
                "tag": s.get("tag"),
                "original_daily_rate": rate,
                "man_days": md,
                "original_labor": lp,
                "normalized_labor_at_725": norm_labor,
                "labor_adjustment_factor": round(labor_adjustment_factor, 4) if labor_adjustment_factor else None,
                "original_labor_per_sf": round(orig_labor_per_sf, 4) if orig_labor_per_sf else None,
                "normalized_labor_per_sf": round(norm_labor_per_sf, 4) if norm_labor_per_sf else None,
                "square_footage": sf,
                "scope_type_normalized": s["scope_type"],
            }
        )

    # Compute normalization impact by scope type
    norm_by_type: dict[str, dict] = {}
    for stype in SCOPE_TYPE_ORDER:
        subset = [r for r in normalized_records if r["scope_type"] == stype]
        factors = [r["labor_adjustment_factor"] for r in subset if r["labor_adjustment_factor"]]
        orig_lpsf = [r["original_labor_per_sf"] for r in subset if r["original_labor_per_sf"]]
        norm_lpsf = [r["normalized_labor_per_sf"] for r in subset if r["normalized_labor_per_sf"]]
        norm_by_type[stype] = {
            "n": len(subset),
            "adjustment_factor": _stats(factors),
            "original_labor_per_sf": _stats(orig_lpsf),
            "normalized_labor_per_sf_at_725": _stats(norm_lpsf),
        }

    # --- Build final output ---
    return {
        "metadata": {
            "current_labor_rate_per_day": CURRENT_LABOR_RATE,
            "analysis_note": (
                "All quote_date fields are NULL in DB — extraction did not populate dates. "
                "12 of 127 project JSON files contain partial dates (many malformed). "
                "Labor rate (daily_labor_rate) is used as temporal proxy for era grouping. "
                "Time-series analysis is approximated by labor rate era, not calendar date."
            ),
            "total_scopes": total,
            "scopes_with_quote_date": with_date,
            "scopes_with_cost_per_unit": with_cost,
            "scopes_with_man_days": with_man_days,
            "scopes_with_daily_labor_rate": with_labor_rate,
            "date_coverage_pct": round(with_date / total * 100, 1) if total else 0,
            "cost_coverage_pct": round(with_cost / total * 100, 1) if total else 0,
        },
        "per_scope_type": per_type_stats,
        "labor_rate_distribution": dict(rate_buckets),
        "era_analysis": era_analysis,
        "labor_normalization": {
            "target_rate": CURRENT_LABOR_RATE,
            "records_normalized": len(normalized_records),
            "by_scope_type": norm_by_type,
            "all_records": normalized_records,
        },
    }


def print_summary(result: dict) -> None:
    """Print a formatted summary table to stdout."""
    meta = result["metadata"]
    per_type = result["per_scope_type"]
    norm = result["labor_normalization"]

    print("\n" + "=" * 80)
    print("ACOUSTIMATOR — PHASE 2.3 HISTORICAL PRICE INDEX REPORT")
    print("=" * 80)

    print("\n[DATA COVERAGE]")
    print(f"  Total scopes:             {meta['total_scopes']}")
    n_date = meta["scopes_with_quote_date"]
    n_cost = meta["scopes_with_cost_per_unit"]
    print(f"  With quote_date:          {n_date}  ({meta['date_coverage_pct']}%)")
    print(f"  With cost_per_unit:       {n_cost}  ({meta['cost_coverage_pct']}%)")
    print(f"  With man_days:            {meta['scopes_with_man_days']}")
    print(f"  With daily_labor_rate:    {meta['scopes_with_daily_labor_rate']}")
    print(f"\n  NOTE: {meta['analysis_note']}")

    print("\n" + "-" * 80)
    print("COST/SF BY SCOPE TYPE  (vs. ANALYSIS.md benchmarks)")
    print("-" * 80)
    hdr = f"{'Type':<8} {'N':>4} {'CostN':>6} {'Mean$/SF':>9} {'Median':>8} {'Std':>7} {'Min':>7} {'Max':>8}  {'Benchmark Range'}"
    print(hdr)
    print("-" * 80)
    for stype in SCOPE_TYPE_ORDER:
        stats = per_type[stype]
        cs = stats["cost_per_unit"]
        bench = stats["benchmark"]
        brange = f"${bench.get('min', '?'):.0f}–${bench.get('max', '?'):.0f}" if bench else "N/A"
        if cs["n"] > 0:
            row = (
                f"{stype:<8} {stats['total_scopes']:>4} {cs['n']:>6} "
                f"{cs['mean']:>9.2f} {cs['median']:>8.2f} {cs['std']:>7.2f} "
                f"{cs['min']:>7.2f} {cs['max']:>8.2f}  {brange}"
            )
        else:
            row = f"{stype:<8} {stats['total_scopes']:>4} {'—':>6}  (no cost_per_unit data)     {brange}"
        print(row)

    print("\n" + "-" * 80)
    print("MARKUP % BY SCOPE TYPE")
    print("-" * 80)
    hdr2 = f"{'Type':<8} {'N':>4} {'Mean%':>7} {'Median%':>8} {'Min%':>6} {'Max%':>6}  {'Benchmark Typical'}"
    print(hdr2)
    print("-" * 80)
    for stype in SCOPE_TYPE_ORDER:
        stats = per_type[stype]
        ms = stats["markup_pct"]
        bench = stats["benchmark"]
        btypical = (
            f"{bench.get('typical_markup_min', 0) * 100:.0f}%–{bench.get('typical_markup_max', 0) * 100:.0f}%"
            if bench
            else "N/A"
        )
        if ms["n"] > 0:
            row = (
                f"{stype:<8} {ms['n']:>4} {ms['mean']:>7.1f} {ms['median']:>8.1f} "
                f"{ms['min']:>6.1f} {ms['max']:>6.1f}  {btypical}"
            )
        else:
            row = f"{stype:<8} {'—':>4}  (no markup data)  {btypical}"
        print(row)

    print("\n" + "-" * 80)
    print("LABOR RATE DISTRIBUTION (all scopes — rate = temporal proxy)")
    print("-" * 80)
    dist = result["labor_rate_distribution"]
    total_rated = sum(dist.values())
    for era_name in sorted(dist.keys()):
        count = dist[era_name]
        pct = count / total_rated * 100 if total_rated else 0
        bar = "#" * int(pct / 2)
        print(f"  {era_name:<45} {count:>4} scopes ({pct:>5.1f}%)  {bar}")

    print("\n" + "-" * 80)
    print(f"LABOR NORMALIZATION IMPACT  (normalizing all costs to ${CURRENT_LABOR_RATE}/day)")
    print("-" * 80)
    hdr3 = f"{'Type':<8} {'N':>4} {'AvgFactor':>10} {'OrigLabor/SF':>13} {'NormLabor/SF':>13}  Avg uplift"
    print(hdr3)
    print("-" * 80)
    for stype in SCOPE_TYPE_ORDER:
        nb = norm["by_scope_type"][stype]
        if nb["n"] == 0:
            print(f"{stype:<8} {'—':>4}  (no data)")
            continue
        af = nb["adjustment_factor"]
        ol = nb["original_labor_per_sf"]
        nl = nb["normalized_labor_per_sf_at_725"]
        factor_mean = af["mean"] if af["mean"] is not None else 0
        uplift = (factor_mean - 1) * 100
        ol_mean = ol["mean"] if ol["mean"] is not None else 0
        nl_mean = nl["mean"] if nl["mean"] is not None else 0
        print(f"{stype:<8} {nb['n']:>4} {factor_mean:>10.3f} {ol_mean:>13.4f} {nl_mean:>13.4f}  {uplift:+.1f}%")

    print("\n" + "-" * 80)
    print("OUTLIERS BY SCOPE TYPE (vs. ANALYSIS.md benchmarks)")
    print("-" * 80)
    for stype in SCOPE_TYPE_ORDER:
        stats = per_type[stype]
        if stats["outlier_count"] == 0:
            continue
        print(f"\n  {stype}:  {stats['outlier_count']} outlier(s)")
        for o in stats["outliers"][:5]:
            print(f"    - {o['project']} [{o.get('tag', '?')}] ${o['cost_per_unit']:.2f}/SF — {', '.join(o['flags'])}")
        if stats["outlier_count"] > 5:
            print(f"    ... and {stats['outlier_count'] - 5} more (see price_index.json)")

    print("\n" + "-" * 80)
    print("ERA TREND ANALYSIS (labor rate as chronological proxy)")
    print("-" * 80)
    era_data = result["era_analysis"]
    for _, _, era_name in LABOR_RATE_ERAS:
        ed = era_data.get(era_name, {})
        if ed.get("scope_count", 0) == 0:
            continue
        cs = ed.get("overall_cost_per_unit", {})
        print(f"\n  {era_name}  [{ed['scope_count']} scopes]")
        if cs.get("n", 0) > 0:
            print(
                f"    Cost/SF: mean=${cs['mean']:.2f}  median=${cs['median']:.2f}  "
                f"range=[${cs['min']:.2f}–${cs['max']:.2f}]  n={cs['n']}"
            )
            for st, sv in ed["by_scope_type"].items():
                if sv["n"] > 0:
                    print(f"      {st}: mean=${sv['mean']:.2f}  n={sv['n']}")
        else:
            print("    No cost_per_unit data for this era")

    print("\n" + "=" * 80)
    print("Output saved to: data/extracted/price_index.json")
    print("=" * 80 + "\n")


async def main() -> None:
    print("Fetching scopes from database...")
    scopes = await fetch_scopes()
    print(f"Loaded {len(scopes)} scopes.")

    print("Running price index analysis...")
    result = analyze(scopes)

    # Save to data/extracted/price_index.json
    out_path = Path(__file__).parent.parent / "data" / "extracted" / "price_index.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print_summary(result)


if __name__ == "__main__":
    asyncio.run(main())
