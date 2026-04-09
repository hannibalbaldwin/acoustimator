#!/usr/bin/env python
"""Phase 7.2 — Retrain cost/markup/labor models and compare performance.

Usage:
    uv run python scripts/retrain_models.py [--force] [--dry-run]

Options:
    --force     Skip the should_retrain check and retrain unconditionally.
    --dry-run   Compute new MAPE but do NOT overwrite .joblib files.

Reads training data from data/models/training_data.csv (created by train_models.py).
Prints a comparison table and updates model_manifest.json.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("retrain_models")

MODELS_DIR = ROOT / "data" / "models"
TRAINING_CSV = MODELS_DIR / "training_data.csv"

# ANSI colours
RESET = "\033[0m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
AMBER = "\033[93m"


def _pct(v: float | None) -> str:
    if v is None or v == float("inf"):
        return "   N/A  "
    return f"{v * 100:6.1f}%"


def _delta_str(old: float | None, new: float) -> str:
    if old is None or new == float("inf"):
        return "   —   "
    delta = (new - old) * 100
    sign = "+" if delta >= 0 else ""
    color = GREEN if delta <= 0 else RED
    return f"{color}{sign}{delta:.1f}pp{RESET}"


def print_table(results: dict) -> None:
    from src.models.retrainer import RetrainResult

    header = f"\n{BOLD}{'Scope/Model':<14} {'Old MAPE':>9} {'New MAPE':>9} {'Delta':>10} {'Deploy':>8}  Reason{RESET}"
    sep = "─" * 80
    print(f"\n{sep}")
    print(header)
    print(sep)
    for name, result in results.items():
        if not isinstance(result, RetrainResult):
            continue
        tick = f"{GREEN}YES{RESET}" if result.deployed else f"{RED}no{RESET}"
        print(
            f"  {name:<12} {_pct(result.old_mape):>9} {_pct(result.new_mape):>9}"
            f"  {_delta_str(result.old_mape, result.new_mape):>10}  {tick:>8}  {result.reason}"
        )
    print(sep)


async def check_should_retrain() -> tuple[bool, str]:
    """Connect to DB and run should_retrain check."""
    from src.db.session import async_session
    from src.models.retrainer import ModelRetrainer

    retrainer = ModelRetrainer()
    async with async_session() as session:
        return await retrainer.should_retrain(session)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrain Acoustimator ML models")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip the should_retrain check and retrain unconditionally",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute new MAPE but do NOT overwrite .joblib files",
    )
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Phase 7.2 — Model Retraining Pipeline{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")

    if args.dry_run:
        print(f"\n  {AMBER}[DRY RUN] No models will be overwritten.{RESET}")

    # ── Should we retrain? ────────────────────────────────────────────
    if not args.force:
        print("\n  Checking retrain conditions...")
        try:
            should, reason = asyncio.run(check_should_retrain())
        except Exception as exc:
            logger.warning("DB check failed (%s) — proceeding anyway", exc)
            should = True
            reason = "DB check unavailable"

        if not should:
            print(f"\n  {YELLOW}Retrain not needed:{RESET} {reason}")
            print("  Use --force to retrain unconditionally.\n")
            return

        print(f"\n  {GREEN}Retrain triggered:{RESET} {reason}")
    else:
        print(f"\n  {YELLOW}--force set — skipping retrain check{RESET}")

    # ── Training CSV ──────────────────────────────────────────────────
    if not TRAINING_CSV.exists():
        print(
            f"\n  {RED}ERROR:{RESET} Training CSV not found at:\n"
            f"  {TRAINING_CSV}\n"
            "  Run 'uv run python scripts/train_models.py' first to generate it.\n"
        )
        sys.exit(1)

    print(f"\n  Training data : {TRAINING_CSV}")

    # ── Retrain ───────────────────────────────────────────────────────
    from src.models.retrainer import ModelRetrainer

    retrainer = ModelRetrainer()

    print("\n  Training new models (this may take a few minutes)...\n")
    try:
        results = retrainer.retrain_all(TRAINING_CSV)
    except Exception as exc:
        print(f"\n  {RED}ERROR during retraining:{RESET} {exc}\n")
        logger.exception("Retraining failed")
        sys.exit(1)

    # ── Print comparison table ────────────────────────────────────────
    print_table(results)

    # ── Deploy ────────────────────────────────────────────────────────
    if args.dry_run:
        # Mark all as deployed=False for dry-run reporting purposes
        from src.models.retrainer import RetrainResult

        for name in list(results.keys()):
            r = results[name]
            if isinstance(r, RetrainResult) and r.deployed:
                results[name] = RetrainResult(
                    scope_type=r.scope_type,
                    old_mape=r.old_mape,
                    new_mape=r.new_mape,
                    deployed=False,
                    reason=f"[dry-run] {r.reason}",
                )
        deployed: list[str] = []
        print(f"\n  {AMBER}[DRY RUN] No .joblib files were written.{RESET}")
    else:
        deployed = retrainer.deploy_if_better(results)
        if deployed:
            print(f"\n  {GREEN}Deployed models:{RESET} {', '.join(deployed)}")
        else:
            print(f"\n  {YELLOW}No models deployed{RESET} (none improved sufficiently).")

    # ── Update manifest ───────────────────────────────────────────────
    if not args.dry_run:
        retrainer.update_manifest(results, deployed)
        print(f"  Manifest updated: {MODELS_DIR / 'model_manifest.json'}")

    print()


if __name__ == "__main__":
    main()
