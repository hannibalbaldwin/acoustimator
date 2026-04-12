"""Root conftest — shared markers and path fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

DROPBOX_ROOT = Path("/Users/hannibalbaldwin/Library/CloudStorage/Dropbox-SiteZeus/Hannibal Baldwin/+ITBs")
DATA_EXTRACTED_PLANS = Path("data/extracted/plans")

# ---------------------------------------------------------------------------
# Skip markers
# ---------------------------------------------------------------------------

requires_dropbox = pytest.mark.skipif(
    not DROPBOX_ROOT.exists(),
    reason="Dropbox +ITBs folder not accessible on this machine",
)
requires_models = pytest.mark.skipif(
    not Path("data/models/ACT_cost_model.joblib").exists(),
    reason="ML model files not available (run scripts/train_models.py first)",
)
requires_extracted_plans = pytest.mark.skipif(
    not DATA_EXTRACTED_PLANS.exists(),
    reason="data/extracted/plans/ not available",
)


# ---------------------------------------------------------------------------
# Path fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dropbox_root() -> Path:
    """Return the root Dropbox +ITBs path."""
    return DROPBOX_ROOT


@pytest.fixture
def seven_pines_pdf(dropbox_root: Path) -> Path:
    """Return the path to the Seven Pines Jax takeoff PDF."""
    return dropbox_root / "+Seven Pines Jax" / "Seven Pines Jax - Takeoff Dwgs.pdf"


@pytest.fixture
def brandon_library_pdf(dropbox_root: Path) -> Path:
    """Return the path to the Brandon Library Replacement takeoff PDF."""
    return dropbox_root / "+Brandon Library Replacement" / "Brandon Library Replace - Acoustic Takeoff.pdf"
