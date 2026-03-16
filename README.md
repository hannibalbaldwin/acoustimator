# Acoustimator

**AI-powered estimation engine for Commercial Acoustics**

## Overview

Commercial Acoustics (Tampa, FL) specializes in acoustical ceiling tile, wall panels, baffles, fabric walls, sound masking, and woodwork installations for commercial, healthcare, education, and hospitality projects across Florida.

Over 500 historical client projects (125 active + 379 archive) live in Dropbox — comprising ~5,000+ files including Excel buildups, customer-facing quote PDFs, vendor quotes, marked-up architectural drawings, and correspondence. These files represent years of hard-won pricing knowledge, but the data is locked in semi-structured spreadsheets and scattered documents.

**Acoustimator** ingests that historical data, normalizes it into a structured database, trains parametric cost models on real project outcomes, and uses AI vision to read architectural plans — producing accurate estimates for new jobs in minutes instead of hours.

## Planned Features

- **Historical Data Extraction** — Parse 500+ project folders (Excel buildups, quote PDFs, vendor quotes, emails) into a structured database using openpyxl and Claude API
- **Parametric Cost Modeling** — Train scope-specific models (ACT, AWP, Baffles, Fabric Wall, WoodWorks, etc.) that predict cost/SF, markup, and labor from project parameters
- **AI Plan Reading** — Upload architectural drawings and let Claude Vision extract rooms, ceiling types, square footages, and suggested scope types
- **Automated Buildup Generation** — Combine plan reading output with cost models to produce full buildups matching the existing Excel format
- **Quote Generation** — Auto-generate customer-facing quotes using the T-004B template
- **Confidence Scoring** — Every estimate includes a confidence score and references to similar historical projects
- **Continuous Learning** — Feedback loop from actual project costs to retrain and improve models over time

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy (async) |
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| Database | Neon serverless PostgreSQL |
| AI | Claude API (sonnet) — extraction + vision |
| ML | scikit-learn, XGBoost, pandas |
| Data Extraction | openpyxl, PyMuPDF, python-docx, extract-msg |
| Infrastructure | Vercel (frontend + backend), Neon (DB), GitHub Actions |

## Project Structure

```
acoustimator/
├── docs/           # Analysis, roadmap, tech stack, schema docs
├── src/
│   ├── extraction/ # Data extraction pipeline (Excel, PDF, plans)
│   ├── models/     # ML cost/labor/markup models
│   ├── estimation/ # Estimation engine combining models + plan reading
│   ├── api/        # FastAPI backend
│   └── db/         # Database models and migrations
├── frontend/       # Next.js web application
├── scripts/        # Utility scripts (batch extract, train, seed)
├── tests/          # Test suite
├── data/           # Local data directory (gitignored)
└── notebooks/      # Jupyter notebooks for exploration
```

See [docs/REPO_STRUCTURE.md](docs/REPO_STRUCTURE.md) for detailed directory documentation.

## Getting Started

> **Note:** This project is in early development. The instructions below will be updated as the setup stabilizes.

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Node.js 20+ and pnpm (for frontend)
- Anthropic API key

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/acoustimator.git
cd acoustimator

# Install Python dependencies
uv sync

# Copy environment variables
cp .env.example .env
# Edit .env with your Anthropic API key and data paths

# Run extraction pipeline (Phase 1)
python scripts/extract_all.py

# Run tests
pytest
```

### Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
DATA_SOURCE_PATH=/path/to/dropbox/+ITBs
DATABASE_URL=postgresql+asyncpg://user:pass@ep-xyz.us-east-2.aws.neon.tech/acoustimator?sslmode=require
```

## Documentation

- [Data Analysis](docs/ANALYSIS.md) — Deep dive into the 500+ project dataset
- [Development Roadmap](docs/ROADMAP.md) — Phased build plan
- [Tech Stack](docs/TECH_STACK.md) — Technology choices and rationale
- [Repository Structure](docs/REPO_STRUCTURE.md) — Directory organization
- [Database Schema](docs/DATA_SCHEMA.md) — Table definitions and relationships

## License

MIT License. See [LICENSE](LICENSE) for details.
