# Acoustimator Repository Structure

Detailed documentation of the repository organization. Every directory and key file is explained.

---

## Top-Level Layout

```
acoustimator/
├── README.md                    # Project overview, getting started
├── CLAUDE.md                    # Claude Code project instructions
├── .gitignore                   # Git exclusions (data/, .env, models/)
├── .env.example                 # Required environment variables template
├── docker-compose.yml           # Multi-service development environment
├── pyproject.toml               # Python project config, dependencies, tool settings
├── uv.lock                      # Locked dependency versions
│
├── docs/                        # Project documentation
├── src/                         # Python source code (all backend logic)
├── frontend/                    # Next.js web application
├── scripts/                     # Utility and batch processing scripts
├── tests/                       # Test suite
├── data/                        # Local data directory (gitignored)
└── notebooks/                   # Jupyter notebooks for exploration
```

---

## docs/ — Project Documentation

```
docs/
├── ANALYSIS.md              # Deep data analysis of the 127-project dataset
├── ROADMAP.md               # Phased development plan
├── TECH_STACK.md            # Technology choices and rationale
├── REPO_STRUCTURE.md        # This file — directory organization
├── DATA_SCHEMA.md           # Database table definitions and relationships
└── API_REFERENCE.md         # API endpoint documentation (Phase 6)
```

All project documentation lives here. These are living documents updated as the project evolves. The analysis document is the canonical reference for understanding the source data. The schema document is the single source of truth for database structure.

---

## src/ — Python Source Code

All backend Python code lives under `src/`. The package is organized by functional layer, following the extraction -> modeling -> estimation pipeline architecture.

### src/extraction/ — Data Extraction Pipeline (Phase 1)

```
src/extraction/
├── __init__.py
├── excel_parser.py          # openpyxl + Claude API buildup extraction
├── pdf_parser.py            # Quote and vendor quote PDF parsing
├── plan_reader.py           # Architectural plan vision AI (Phase 4)
├── msg_parser.py            # Outlook email extraction
└── validators.py            # Data validation rules
```

**excel_parser.py** — The most critical module. Reads Excel buildups using openpyxl, constructs a text representation of the cell grid, sends it to Claude API for field extraction, and returns structured `ScopeExtraction` objects. Handles all three buildup format types (A: simple, B: multi-scope, C: multi-building).

**pdf_parser.py** — Extracts data from customer-facing quote PDFs (template T-004B) and vendor quote PDFs. Uses PyMuPDF for text extraction from structured templates; falls back to Claude Vision for non-standard formats.

**plan_reader.py** — Phase 4 module. Renders PDF plan pages to images, sends to Claude Vision API, and extracts rooms, areas, ceiling types, and scope suggestions from architectural drawings.

**msg_parser.py** — Parses Outlook .msg files using extract-msg. Extracts sender, date, subject, body, and attachments. Lower priority — supplementary data source.

**validators.py** — Validation functions applied to all extracted data. Checks for required fields, value ranges (e.g., markup 0-100%, SF > 0), formula consistency (total = material_price + labor_price + sales_tax), and cross-references between buildups and quotes.

### src/models/ — Machine Learning Models (Phase 3)

```
src/models/
├── __init__.py
├── cost_model.py            # Parametric cost/SF estimation
├── labor_model.py           # Man-day prediction from SF and scope type
├── markup_model.py          # Markup percentage prediction
├── features.py              # Feature engineering pipeline
└── training.py              # Model training and evaluation
```

**cost_model.py** — Per-scope-type models that predict cost/SF from project parameters. Wraps scikit-learn Random Forest / XGBoost with domain-specific preprocessing.

**labor_model.py** — Predicts man-days from square footage, scope type, and project complexity. Accounts for fixed setup time plus variable production time.

**markup_model.py** — Predicts appropriate markup percentage based on scope type, project type, client type, and competitive factors.

**features.py** — Feature engineering pipeline. Transforms raw extracted data into model-ready feature matrices. Handles categorical encoding, derived features (project size category, product tier), and feature scaling.

**training.py** — Model training orchestration. Cross-validation, hyperparameter tuning, model selection, performance evaluation, and model serialization (pickle/joblib).

### src/estimation/ — Estimation Engine (Phase 5)

```
src/estimation/
├── __init__.py
├── estimator.py             # Core estimation logic
├── buildup_generator.py     # Excel buildup output generation
├── comparables.py           # Historical project similarity matching
└── confidence.py            # Estimate confidence scoring
```

**estimator.py** — The central orchestrator. Takes plan reading output (or manual input), runs it through the cost, markup, and labor models, and produces a complete estimate with all scope-level details.

**buildup_generator.py** — Generates Excel buildups matching the existing Format B template. Uses openpyxl to create formatted .xlsx files with proper column widths, number formats, and summary rows.

**comparables.py** — Finds the most similar historical projects to a given estimate. Uses feature-based similarity (cosine distance on normalized scope/SF/product vectors) to rank historical projects by relevance.

**confidence.py** — Calculates confidence scores for each estimate component. Based on model prediction uncertainty, training data density near the input point, and plan reading clarity.

### src/api/ — FastAPI Backend (Phase 6)

```
src/api/
├── __init__.py
├── main.py                  # FastAPI app entry point, middleware, CORS
├── routes/
│   ├── estimates.py         # Estimate CRUD, generation, export endpoints
│   ├── projects.py          # Historical project browsing endpoints
│   └── uploads.py           # Plan PDF upload and processing endpoints
└── deps.py                  # Dependencies: DB session, auth, rate limiting
```

**main.py** — FastAPI application factory. Configures CORS, mounts routes, sets up exception handlers, and initializes database connection.

**routes/estimates.py** — Endpoints for creating, retrieving, updating, and exporting estimates. Includes the main estimation workflow endpoint that accepts uploaded plans and returns a generated estimate.

**routes/projects.py** — Read-only endpoints for browsing the historical project database. Supports filtering by scope type, date range, project type, and GC name.

**routes/uploads.py** — File upload endpoints for architectural plan PDFs. Handles multipart uploads, stores files, and triggers the plan reading pipeline.

**deps.py** — FastAPI dependency injection functions. Provides database sessions, authentication checks, and rate limiting.

### src/db/ — Database Layer

```
src/db/
├── __init__.py
├── models.py                # SQLAlchemy ORM model definitions
├── session.py               # Database connection and session management
└── migrations/              # Alembic migration scripts
    ├── env.py
    ├── alembic.ini
    └── versions/
```

**models.py** — SQLAlchemy ORM models corresponding to the tables in [DATA_SCHEMA.md](DATA_SCHEMA.md). Defines Projects, Scopes, Products, Vendors, VendorQuotes, Estimates, and EstimateScopes.

**session.py** — Database engine creation and session factory. Reads DATABASE_URL from environment, creates the SQLAlchemy engine, and provides a session dependency for FastAPI.

**migrations/** — Alembic migration directory. Auto-generated migration scripts track schema changes. Run with `alembic upgrade head` to apply.

### src/config.py — Application Configuration

Pydantic BaseSettings class that reads configuration from environment variables and `.env` file. Defines:
- `ANTHROPIC_API_KEY` — Claude API key
- `DATABASE_URL` — Database connection string
- `DATA_SOURCE_PATH` — Path to Dropbox +ITBs folder
- `LOG_LEVEL` — Logging verbosity
- `MODEL_DIR` — Path to trained model artifacts

---

## frontend/ — Next.js Web Application (Phase 6)

```
frontend/
├── package.json
├── pnpm-lock.yaml
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
│
├── app/
│   ├── layout.tsx           # Root layout with navigation
│   ├── page.tsx             # Dashboard — project stats, recent estimates
│   ├── estimate/
│   │   ├── page.tsx         # New estimate workflow (upload plans)
│   │   └── [id]/
│   │       └── page.tsx     # Estimate detail and editing
│   ├── projects/
│   │   ├── page.tsx         # Historical project browser
│   │   └── [id]/
│   │       └── page.tsx     # Project detail view
│   └── upload/
│       └── page.tsx         # Plan upload and processing status
│
├── components/
│   ├── ui/                  # shadcn/ui components
│   ├── scope-table.tsx      # Scope line item table (shared)
│   ├── estimate-builder.tsx # Interactive estimate editor
│   ├── plan-upload.tsx      # Drag-and-drop upload component
│   ├── project-card.tsx     # Project summary card
│   └── cost-chart.tsx       # Cost trend visualization
│
└── lib/
    ├── api.ts               # API client (fetch wrapper)
    └── types.ts             # TypeScript type definitions
```

The frontend uses Next.js 15 App Router with server components for initial page loads and client components for interactive elements (estimate builder, charts).

---

## scripts/ — Utility Scripts

```
scripts/
├── extract_all.py           # Batch extraction: process all 127+ project folders
├── train_models.py          # Model training: run full training pipeline
└── seed_db.py               # Database seeding: populate from extracted data
```

**extract_all.py** — Main batch processing script. Iterates through all project folders in the Dropbox +ITBs directory, runs the extraction pipeline on each, and loads results into the database. Includes progress reporting, error handling, and resume capability (skips already-extracted projects).

**train_models.py** — Runs the full model training pipeline: loads data from the database, engineers features, trains cost/labor/markup models per scope type, evaluates via cross-validation, and saves the best models to `data/models/`.

**seed_db.py** — Creates the database schema and populates it from JSON extraction outputs in `data/extracted/`. Used for setting up a fresh database from previously extracted data.

---

## tests/ — Test Suite

```
tests/
├── conftest.py              # Shared fixtures (test DB, sample data)
├── test_extraction/
│   ├── test_excel_parser.py # Buildup extraction tests
│   ├── test_pdf_parser.py   # Quote/vendor PDF parsing tests
│   └── fixtures/            # Sample Excel/PDF files for testing
├── test_models/
│   ├── test_cost_model.py   # Cost model training and prediction
│   ├── test_features.py     # Feature engineering tests
│   └── test_training.py     # Training pipeline tests
├── test_estimation/
│   ├── test_estimator.py    # End-to-end estimation tests
│   ├── test_comparables.py  # Historical matching tests
│   └── test_buildup_gen.py  # Excel output generation tests
└── test_api/
    ├── test_estimates.py    # API endpoint tests
    └── test_projects.py     # API endpoint tests
```

Run all tests: `pytest`
Run with coverage: `pytest --cov=src`
Run a specific module: `pytest tests/test_extraction/test_excel_parser.py`

---

## data/ — Local Data (Gitignored)

```
data/
├── raw/                     # Symlink to Dropbox +ITBs folder
├── extracted/               # JSON extraction outputs (one per project)
├── models/                  # Trained model artifacts (.joblib)
└── exports/                 # Generated buildups and quotes
```

The entire `data/` directory is gitignored. It contains:

**raw/** — A symlink to the Dropbox `+ITBs` folder (`/Users/hannibalbaldwin/Library/CloudStorage/Dropbox-SiteZeus/Hannibal Baldwin/+ITBs`). This avoids copying 186MB of source files into the repo.

**extracted/** — JSON files containing structured extraction results for each project. One file per project folder. These serve as a cache — if extraction needs to be re-run, only changed projects are reprocessed.

**models/** — Serialized scikit-learn models (.joblib format). One model per scope type per model type (e.g., `act_cost_rf.joblib`, `awp_cost_xgb.joblib`).

**exports/** — Generated Excel buildups and PDF quotes from the estimation engine.

---

## notebooks/ — Jupyter Notebooks

```
notebooks/
├── 01_data_exploration.ipynb    # EDA on extracted dataset
├── 02_extraction_testing.ipynb  # Interactive extraction development
└── 03_model_training.ipynb      # Model experimentation
```

Jupyter notebooks for exploration and prototyping. These are development tools, not production code. They may fall out of date as the codebase evolves.

**01_data_exploration.ipynb** — Exploratory data analysis: distribution of costs, scope types, project sizes, markup ranges, labor rates, and vendor pricing trends.

**02_extraction_testing.ipynb** — Interactive development of the extraction pipeline. Test Claude API prompts on individual buildups, inspect results, and iterate on extraction logic before committing to `src/extraction/`.

**03_model_training.ipynb** — Model experimentation: feature selection, model comparison (RF vs. XGBoost vs. linear regression), hyperparameter tuning, and performance visualization.
