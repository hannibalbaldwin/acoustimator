# Acoustimator — Claude Code Project Instructions

## Project Overview

Acoustimator is an AI-powered estimation engine for Commercial Acoustics (Tampa, FL). It ingests 500+ historical client projects (125 active + 379 archive) comprising ~5,000+ files (Excel buildups, quote PDFs, vendor quotes, architectural drawings) and uses that data to estimate new jobs from plans/drawings.

## Source Data Location

The raw project data is at:
```
/Users/hannibalbaldwin/Library/CloudStorage/Dropbox-SiteZeus/Hannibal Baldwin/+ITBs
```

This contains 126 folders (125 active projects + 1 `++Archive` with 379 historical projects) totaling ~5,000+ files (2,928 PDFs, 823 xlsx, 621 doc/docx, 304 msg, etc.). See `docs/ANALYSIS.md` for the full data analysis.

## Tech Stack

- **Python 3.12+** backend with **uv** for package management
- **Next.js 15** frontend with **pnpm** for package management
- **Neon** serverless PostgreSQL (pooled endpoint for app, direct endpoint for migrations)
- **Claude API (claude-sonnet-4-6)** for data extraction and plan reading
- **scikit-learn / XGBoost** for parametric cost models
- **FastAPI** for the API layer

## Infrastructure

- **Database:** Neon serverless Postgres — branch-per-environment (`main` = prod, `dev`, `staging`, auto-branches for Vercel previews)
- **Frontend deploy:** Vercel (Hobby tier, $0/mo)
- **Backend deploy:** Vercel serverless function (same project, $0/mo) — FastAPI runs as a native Python serverless function
- **Local dev:** Connect directly to Neon `dev` branch (no local Postgres needed), or use `docker-compose.yml` for local services

## Commands

```bash
# Install Python dependencies
uv sync

# Run tests
pytest

# Run tests with coverage
pytest --cov=src

# Lint and format
ruff check src/ tests/
ruff format src/ tests/

# Run the API server (Phase 6)
uvicorn src.api.main:app --reload

# Run batch extraction
python scripts/extract_all.py

# Train models
python scripts/train_models.py

# Frontend (in frontend/ directory)
pnpm install
pnpm dev
```

## Architecture

The project follows a pipeline architecture: **extraction -> modeling -> estimation**.

```
src/
├── extraction/    # Phase 1: Parse Excel, PDF, plans, emails into structured data
├── models/        # Phase 3: Train and serve cost/labor/markup ML models
├── estimation/    # Phase 5: Combine plan reading + models into full estimates
├── api/           # Phase 6: FastAPI endpoints
├── db/            # Database models and migrations
└── config.py      # Application configuration
```

## Code Style

- Always use type hints in Python code
- Use Pydantic models for data validation and serialization
- Use SQLAlchemy 2.0 style (declarative mappings, new query syntax)
- Follow ruff defaults (line length 100, Python 3.12 target)
- Prefer `decimal.Decimal` for monetary values, not `float`
- All extraction functions should return structured Pydantic models, not raw dicts

## Domain Terminology

- **Buildup** — Internal Excel cost spreadsheet with material, labor, and tax calculations
- **Takeoff** — Process of measuring quantities from architectural drawings
- **Scope** — A line item category (e.g., ACT-1 for ceiling tile in area 1, AWP-1 for wall panels)
- **Man-days** — Unit of labor (one crew working one day, ~$522-558/day loaded rate)
- **ACT** — Acoustical Ceiling Tile
- **AWP** — Acoustic Wall Panels
- **FW** — Fabric Wall (Snap-Tex track system)
- **SM** — Sound Masking
- **WW** — WoodWorks (wood ceiling systems)
- **RPG** — Specialty acoustic diffusers
- **GC** — General Contractor (the client in most projects)
- **SF** — Square Feet (primary unit of measure)
- **LF** — Linear Feet (for baffles, track, trim)
- **T-004B** — The standard quote template used by Commercial Acoustics
- **Markup** — Percentage margin applied to material cost (ranges 15%-75%)

## Database Schema

See `docs/DATA_SCHEMA.md` for complete table definitions. Core tables:
- `projects` — One per client project folder
- `scopes` — Individual cost line items within a project
- `products` — Normalized product catalog
- `vendors` / `vendor_quotes` — Supplier pricing data
- `estimates` / `estimate_scopes` — AI-generated estimates

## Key Files

- `docs/ANALYSIS.md` — Deep data analysis (start here to understand the domain)
- `docs/ROADMAP.md` — Phased development plan
- `docs/DATA_SCHEMA.md` — Database schema
- `src/extraction/excel_parser.py` — Core buildup extraction logic
- `src/extraction/plan_reader.py` — AI plan reading (Phase 4)
- `src/models/cost_model.py` — Parametric cost estimation
- `src/estimation/estimator.py` — End-to-end estimation engine

## Testing

- Test fixtures (sample Excel/PDF files) go in `tests/test_extraction/fixtures/`
- Use pytest fixtures in `tests/conftest.py` for shared test data
- Mock Claude API calls in tests — do not make real API calls in CI
- Target 80%+ code coverage for extraction and estimation modules

## Data Handling

- The `data/` directory is gitignored — never commit raw data, model artifacts, or exports
- `data/raw/` should be a symlink to the Dropbox +ITBs folder
- Extracted JSON outputs go in `data/extracted/`
- Trained models go in `data/models/`
- Never hardcode file paths — use `src/config.py` settings
