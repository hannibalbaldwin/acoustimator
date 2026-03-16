# Acoustimator Tech Stack

Detailed technology choices for the Acoustimator estimation engine, with rationale for each decision.

---

## Core Languages

### Python 3.12+

**Role:** Backend, data extraction, ML modeling, API server

Python is the natural choice for this project given the heavy data extraction, machine learning, and API requirements. The ecosystem for Excel parsing (openpyxl), PDF processing (PyMuPDF), ML (scikit-learn), and web APIs (FastAPI) is unmatched.

Python 3.12+ is specified for:
- Improved error messages (better debugging during extraction development)
- Performance improvements (10-15% faster than 3.11)
- `type` statement for cleaner type alias definitions

### TypeScript

**Role:** Frontend (Next.js)

TypeScript provides type safety for the frontend application, catching errors at compile time and improving developer experience with autocompletion. All frontend code is written in TypeScript with strict mode enabled.

### SQL

**Role:** Database queries, migrations, reporting

Raw SQL is used for complex analytical queries (cost trend analysis, similar project matching). SQLAlchemy ORM handles standard CRUD operations.

---

## Data Extraction Layer

### openpyxl

**Role:** Excel file reading (.xlsx format)

```
pip: openpyxl>=3.1.0
```

Used to read cell values, sheet names, and workbook structure from the 421 Excel buildups. Key features used:
- `load_workbook(data_only=True)` — read calculated values, not formulas
- Iterating rows and columns to build cell grids
- Reading merged cell ranges
- Sheet name enumeration for multi-sheet workbooks

**Why not pandas?** Buildups are not tabular data — they lack consistent headers and have variable layouts. openpyxl gives cell-level access needed for semi-structured extraction.

### Claude API (claude-sonnet-4-6)

**Role:** Semi-structured data extraction from Excel cell grids, intelligent field mapping

```
pip: anthropic>=0.40.0
```

The core AI engine for the extraction pipeline. Rather than writing brittle format-specific parsers, the cell grid from openpyxl is sent to Claude as structured text, and Claude extracts the fields intelligently regardless of format (A, B, or C).

**Prompt strategy:**
- System prompt defines the domain (acoustical construction estimation)
- User prompt contains the cell grid as a formatted table
- Tool use / structured output for consistent JSON responses
- Validation layer checks extracted values for sanity

**Cost estimate:** ~$0.01 per buildup extraction (sonnet, ~2K input tokens + 500 output tokens per scope)

### Claude Vision API (claude-sonnet-4-6)

**Role:** PDF plan reading, architectural drawing interpretation

Used in Phase 4+ for reading architectural floor plans and reflected ceiling plans. The Vision API processes rendered PDF pages as images and extracts:
- Room names and boundaries
- Dimensional information
- Ceiling type annotations
- Wall treatment specifications
- Keynote references

**Cost estimate:** ~$0.003 per page (sonnet vision, ~1K image tokens per page)

### PyMuPDF (fitz)

**Role:** PDF text extraction and image rendering

```
pip: PyMuPDF>=1.24.0
```

Used for two purposes:
1. **Text extraction** from structured quote PDFs (template T-004B) where OCR is not needed
2. **Page rendering** to images for Claude Vision API input (plan reading)

PyMuPDF is chosen over alternatives (pdfplumber, pdfminer) for its speed, reliability with complex layouts, and built-in image rendering.

### python-docx

**Role:** Word document parsing (.docx format)

```
pip: python-docx>=1.1.0
```

Used to extract data from the 14 .docx files (bid forms, proposals). Lower priority — most critical data is in Excel and PDF formats.

### extract-msg

**Role:** Outlook .msg file parsing

```
pip: extract-msg>=0.48.0
```

Extracts sender, recipient, date, subject, body, and attachments from the 112 Outlook .msg files. Lowest priority for extraction — emails provide supplementary metadata, not core pricing data.

---

## Database

### SQLite (Phase 1-3, Development)

**Role:** Development database, zero-config, file-based

SQLite is the development database for its simplicity:
- No server process to manage
- Single file (`data/acoustimator.db`) — easy to back up, share, reset
- Full SQL support for analytical queries
- Sufficient for the 127-project dataset (well within SQLite's capabilities)

### PostgreSQL (Phase 4+, Production)

**Role:** Production database, full-featured

PostgreSQL becomes necessary when the web application (Phase 6) requires:
- Concurrent multi-user access
- JSONB columns for flexible vendor quote item storage
- Array columns (text[], UUID[]) for scope tags and aliases
- Full-text search for project and product lookup
- Better indexing for complex analytical queries

### SQLAlchemy

**Role:** ORM and query builder

```
pip: sqlalchemy>=2.0
```

SQLAlchemy 2.0 with the new-style declarative mappings. Provides:
- ORM models mapped to database tables (see [DATA_SCHEMA.md](DATA_SCHEMA.md))
- Session management and connection pooling
- Database-agnostic queries (same code for SQLite and PostgreSQL)
- Relationship definitions (project -> scopes, scope -> product)

### Alembic

**Role:** Database migration management

```
pip: alembic>=1.13.0
```

Manages schema changes as the database evolves. Auto-generates migration scripts from SQLAlchemy model changes. Essential for Phase 4+ when the schema stabilizes and production data must be preserved across updates.

---

## Machine Learning

### scikit-learn

**Role:** Parametric cost models (Random Forest, XGBoost)

```
pip: scikit-learn>=1.4.0
```

Primary ML library for:
- **Random Forest Regressor** — cost/SF prediction per scope type
- **Gradient Boosting (XGBoost)** — alternative ensemble method
- **Cross-validation** — model evaluation with limited data
- **Feature preprocessing** — categorical encoding, scaling
- **Pipeline API** — combine preprocessing and model in a single object

scikit-learn is chosen over deep learning frameworks because the dataset (500-1,000 rows) is too small for neural networks, and tree-based methods excel on small tabular datasets.

### XGBoost

**Role:** Gradient boosted tree models

```
pip: xgboost>=2.0
```

XGBoost provides a scikit-learn-compatible interface with better handling of missing values and built-in feature importance. Used alongside Random Forest to compare performance — the better model is selected per scope type.

### pandas

**Role:** Data manipulation and feature engineering

```
pip: pandas>=2.2.0
```

The standard data manipulation library. Used for:
- Loading extracted data from the database into DataFrames
- Feature engineering (computing derived features like project size category)
- Data exploration and profiling
- Merging datasets (e.g., joining scope data with vendor costs)

### numpy

**Role:** Numerical computations

```
pip: numpy>=1.26.0
```

Underlying numerical engine for pandas and scikit-learn. Used directly for:
- Array operations in feature engineering
- Statistical calculations (percentiles, distributions)
- Random number generation for train/test splits

### matplotlib / plotly

**Role:** Data visualization and model analysis

```
pip: matplotlib>=3.8.0
pip: plotly>=5.18.0
```

- **matplotlib** — Static plots for notebooks and model evaluation (residual plots, feature importance charts, actual vs. predicted scatter)
- **plotly** — Interactive plots for the data quality dashboard and web frontend (cost trends, model performance over time)

---

## Backend API

### FastAPI

**Role:** High-performance async API framework

```
pip: fastapi>=0.110.0
```

FastAPI is the API framework for Phase 6, chosen for:
- Automatic OpenAPI/Swagger documentation
- Pydantic integration for request/response validation
- Async support for concurrent AI API calls
- Dependency injection system for database sessions, auth
- File upload handling for plan PDFs

### Pydantic

**Role:** Data validation and serialization

```
pip: pydantic>=2.6.0
```

Used throughout the project (not just in the API layer):
- Extraction output schemas (structured Claude API responses)
- API request/response models
- Configuration management (BaseSettings)
- Database model serialization

### uvicorn

**Role:** ASGI server

```
pip: uvicorn[standard]>=0.27.0
```

Production-grade ASGI server for FastAPI. Standard extras include uvloop and httptools for maximum performance.

---

## Frontend

### Next.js 15

**Role:** React framework with App Router

```
pnpm: next@15
```

Next.js provides the frontend application framework:
- App Router for file-based routing
- Server Components for initial page loads
- API route handlers for BFF pattern (if needed)
- Built-in image optimization
- Turbopack for fast development builds

### Tailwind CSS

**Role:** Utility-first styling

```
pnpm: tailwindcss@4
```

Tailwind v4 for rapid UI development without writing custom CSS. Provides consistent design system with minimal configuration.

### shadcn/ui

**Role:** Component library

```
pnpm: (installed via CLI, not npm dependency)
```

Accessible, composable component library built on Radix UI primitives. Provides:
- Table components for scope data display
- Dialog/Sheet for estimate editing
- Form components with validation
- File upload dropzone
- Toast notifications

Components are copied into the project (not imported from a package), allowing full customization.

### react-dropzone

**Role:** File upload handling

```
pnpm: react-dropzone
```

Drag-and-drop file upload component for architectural plan PDFs. Handles file type validation, size limits, and upload progress.

### recharts

**Role:** Data visualization in the frontend

```
pnpm: recharts
```

Chart library for the project dashboard:
- Cost/SF trend lines by scope type
- Estimate confidence distribution
- Project volume over time
- Vendor cost comparisons

---

## Infrastructure

### Docker

**Role:** Containerized deployment

Docker Compose for local development with multiple services:
- `api` — FastAPI backend
- `frontend` — Next.js application
- `db` — PostgreSQL (production mode)

Production deployment via single Dockerfile per service.

### GitHub Actions

**Role:** CI/CD pipeline

Workflows:
- **Test** — Run pytest on every PR
- **Lint** — Ruff check on every PR
- **Build** — Docker image build on merge to main
- **Deploy** — Deploy to hosting on release tag

### Hosting (TBD)

Options under consideration:
- **Vercel** — Frontend hosting (native Next.js support)
- **Railway** — Full-stack hosting (API + DB + frontend in one platform)
- **Fly.io** — Container-based hosting (more control, lower cost at scale)

Decision deferred to Phase 6 based on performance and cost requirements.

---

## Development Tools

### uv

**Role:** Python package manager

```
brew: uv
```

Fast Python package manager replacing pip + venv + pip-tools. Used for:
- `uv sync` — Install dependencies from pyproject.toml
- `uv add` — Add new dependencies
- `uv run` — Run commands in the virtual environment
- Lock file (`uv.lock`) for reproducible installs

### pytest

**Role:** Testing framework

```
pip: pytest>=8.0.0
pip: pytest-asyncio>=0.23.0
pip: pytest-cov>=4.1.0
```

Test suite organization:
- `tests/test_extraction/` — Parser tests with fixture Excel/PDF files
- `tests/test_models/` — Model training and prediction tests
- `tests/test_estimation/` — Estimation engine integration tests
- `tests/test_api/` — FastAPI endpoint tests

### ruff

**Role:** Python linting and formatting

```
pip: ruff>=0.3.0
```

Single tool replacing flake8, black, isort, and pyupgrade. Configuration in `pyproject.toml`:
- Line length: 100
- Target: Python 3.12
- Rules: E, F, I, UP, B, SIM, RUF
- Format: black-compatible

### pre-commit

**Role:** Git hook management

```
pip: pre-commit>=3.6.0
```

Hooks configured:
- ruff check (lint)
- ruff format (format)
- mypy (type checking)
- pytest (run fast tests only)

---

## External APIs

### Anthropic Claude API

**Role:** Core AI engine for extraction and plan reading

The single external API dependency. Used for:
1. **Excel buildup extraction** (Phase 1) — Semi-structured data parsing via claude-sonnet-4-6
2. **Vendor quote extraction** (Phase 1) — PDF/image parsing via Claude Vision
3. **Plan reading** (Phase 4) — Architectural drawing interpretation via Claude Vision
4. **Product name normalization** (Phase 2) — Fuzzy matching assistance

**Cost Estimates:**

| Task | Model | Input | Output | Cost/Call | Total (127 projects) |
|------|-------|-------|--------|-----------|---------------------|
| Buildup extraction | claude-sonnet-4-6 | ~2K tokens | ~500 tokens | ~$0.01 | ~$1.27 |
| Quote PDF parsing | claude-sonnet-4-6 | ~1K tokens | ~300 tokens | ~$0.005 | ~$0.50 |
| Vendor quote parsing | claude-sonnet-4-6 vision | ~1K image tokens | ~300 tokens | ~$0.003 | ~$0.25 |
| Plan reading (Phase 4) | claude-sonnet-4-6 vision | ~2K image tokens | ~500 tokens | ~$0.008 | Per job |

**Total extraction cost for entire dataset: < $5.00**

### API Key Management

- API key stored in `.env` file (never committed)
- `.env.example` documents required variables
- Application reads key via Pydantic BaseSettings
- Rate limiting: Anthropic allows 50 RPM on standard tier — sufficient for batch extraction
