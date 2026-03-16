# Acoustimator Development Roadmap

Phased development plan for the Acoustimator estimation engine. Each phase builds on the previous, with clear deliverables and acceptance criteria.

---

## Phase 0: Project Setup & Documentation (Current)

**Goal:** Establish the project foundation — repository, documentation, analysis, and development environment.

### Tasks
- [x] Initialize Git repository
- [x] Deep analysis of the 500+ project dataset (see [ANALYSIS.md](ANALYSIS.md))
- [x] Define database schema (see [DATA_SCHEMA.md](DATA_SCHEMA.md))
- [x] Document tech stack and architecture decisions (see [TECH_STACK.md](TECH_STACK.md))
- [x] Define repository structure (see [REPO_STRUCTURE.md](REPO_STRUCTURE.md))
- [ ] Create `pyproject.toml` with initial dependencies
- [ ] Create `.env.example` with required environment variables
- [ ] Set up `.gitignore` (data/, models/, .env, etc.)
- [ ] Create `CLAUDE.md` project instructions
- [ ] Validate Dropbox data source accessibility
- [ ] Set up Neon project with `main` and `dev` branches
- [ ] Configure Vercel project for both Next.js frontend and FastAPI backend
- [ ] Set up Neon integration on Vercel (auto-branch preview DBs)
- [ ] Configure environment variables across both services (Neon, Vercel)

**Deliverable:** Fully documented project ready for development. Any developer can read the docs and understand the domain, data, and plan.

---

## Phase 1: Data Extraction Pipeline (Week 1-2)

**Goal:** Extract structured data from all 500+ project folders into a normalized database.

### 1.1: Excel Buildup Parser

The most critical component. Buildups are semi-structured Excel files with three format families (see [ANALYSIS.md — Excel Buildup Analysis](ANALYSIS.md#excel-buildup-analysis)).

**Approach:** Use openpyxl to read cell contents, then send the cell grid to Claude API (claude-sonnet-4-6) for intelligent field extraction. Claude handles format detection and field mapping in a single pass.

- Read all cells from each sheet (values, not formulas)
- Build a text representation of the cell grid
- Send to Claude with a structured extraction prompt
- Parse Claude's response into a standardized `ScopeExtraction` schema
- Validate extracted values (SF > 0, markup 0-100%, total = sum of components)
- Handle multi-sheet workbooks (iterate all sheets, skip non-data sheets)

**Acceptance criteria:**
- Successfully extracts data from 90%+ of the 123 buildups with buildups
- Extracted totals match within 2% of quote totals for validation set
- Handles all three format types (A, B, C)

### 1.2: Quote PDF Parser

Extract structured data from customer-facing quote PDFs (template T-004B).

- Use PyMuPDF (fitz) for text extraction from the standardized template
- Extract: quote number, date, client, project address, line items, totals
- Cross-reference with buildup data for validation

**Acceptance criteria:**
- Extract quote number and totals from 95%+ of quote PDFs
- Line item extraction with correct quantities and descriptions

### 1.3: Vendor Quote Parser

Extract pricing data from vendor quote PDFs and emails.

- Use Claude Vision API for non-standard vendor quote formats
- Extract: vendor, products, quantities, unit costs, freight, totals
- Map vendor products to the internal product catalog

**Acceptance criteria:**
- Extract vendor and total from 80%+ of vendor quotes
- Line-item extraction for top 5 vendors (MDC, FBM, GatorGyp, Snap-Tex, RPG)

### 1.4: Data Validation and Quality Checks

Automated validation layer for all extracted data.

- Cross-reference buildup totals with quote totals
- Flag outliers (cost/SF outside expected range per scope type)
- Check for missing required fields
- Generate extraction quality report

### 1.5: Load into Database

Persist all extracted data into the database.

- Create SQLite database with schema from [DATA_SCHEMA.md](DATA_SCHEMA.md)
- Bulk insert all extracted projects, scopes, vendor quotes
- Store extraction metadata (source file, extraction confidence, timestamp)

**Phase 1 Deliverable:** All 500+ projects normalized into a structured SQLite database with quality metrics. Every data point traceable to its source file.

---

## Phase 2: Data Enrichment & Cleaning (Week 2-3)

**Goal:** Transform raw extracted data into a clean, normalized dataset ready for modeling.

### 2.1: Product Name Normalization

Map the ~200+ free-form product name variations to a canonical product catalog.

- Build initial catalog from known products (Armstrong Dune, Cortega, Cirrus, etc.)
- Use fuzzy matching (fuzz ratio > 85%) to map variations to canonical names
- Manual review queue for ambiguous matches
- Store aliases in the `products.aliases` array for future matching

**Examples:**
```
"Dune on Suprafine"           → Armstrong Dune (tile) + Armstrong Suprafine (grid)
"Armstrong Dune #2404 on XL"  → Armstrong Dune (tile) + Armstrong Suprafine XL (grid)
"Lyra PB WoodLook"            → Armstrong Lyra PB (tile), WoodLook finish variant
```

### 2.2: Scope Type Classification

Ensure every scope is classified into one of the 8 canonical types.

- Validate extracted scope tags against known patterns (ACT-*, AWP-*, etc.)
- Classify scopes with non-standard tags using product name and description
- Handle edge cases: "CL" (Cloud) maps to Baffles or ACT depending on product

### 2.3: Historical Price Indexing

Adjust historical prices for time-based cost changes.

- Use quote dates to establish a timeline
- Calculate cost/SF trends per product over time
- Apply inflation adjustment to normalize prices to current dollars
- Track labor rate changes ($522 -> $540 -> $558/day)

### 2.4: Vendor Cost Tracking

Build a vendor price database from extracted vendor quotes.

- Track unit costs per product per vendor over time
- Identify preferred vendors by product category
- Calculate typical freight percentages
- Flag significant price changes

### 2.5: Data Quality Dashboard

Interactive report showing dataset health.

- Total projects extracted, by scope type, by project type
- Missing field rates per field
- Outlier detection results
- Extraction confidence distribution
- Product name normalization coverage

**Phase 2 Deliverable:** Clean, normalized dataset with canonical product names, classified scope types, and time-indexed pricing. Quality dashboard showing dataset health.

---

## Phase 3: Parametric Cost Model (Week 3-4)

**Goal:** Train ML models that predict cost components from project parameters.

### 3.1: Feature Engineering

Design the feature set for cost prediction models.

**Input features (per scope):**
- Square footage (continuous)
- Scope type (categorical: ACT, AWP, etc.)
- Product category (categorical: ceiling_tile, wall_panel, etc.)
- Product tier (ordinal: economy, standard, premium, specialty)
- Project type (categorical: commercial, healthcare, education, etc.)
- Project size (ordinal: small <5K SF, medium 5-20K, large 20K+)
- Number of scopes in project (continuous)
- Client type (categorical: GC, owner-direct)

**Target variables (separate models):**
- Cost/SF (material unit rate)
- Markup % (margin applied)
- Man-days per 1000 SF (labor intensity)

### 3.2: Train Cost Models

Train per-scope-type models for cost/SF prediction.

- **ACT model** (~200+ rows): Random Forest or XGBoost — predict cost/SF from product, project type, SF
- **AWP model** (~80+ rows): Similar approach, add panel type and mounting method features
- **General model** (all scope types): Fallback model using scope type as a feature
- Hyperparameter tuning with cross-validation
- Feature importance analysis

### 3.3: Model Validation

Rigorous validation to ensure models generalize.

- K-fold cross-validation (k=5 for larger scope types, LOOCV for smaller)
- Holdout test set (20% of data, stratified by scope type)
- Error metrics: MAE, MAPE, R-squared
- **Target:** MAPE < 15% for ACT, < 20% for other scope types
- Residual analysis to identify systematic biases

### 3.4: Markup Prediction Model

Predict the appropriate markup percentage for a given scope.

- Features: scope type, project type, client type (GC vs. direct), total project size, competitive intensity (if available)
- Historical markup ranges by scope type as priors
- Output: predicted markup % with confidence interval

### 3.5: Labor Estimation Model

Predict man-days from scope parameters.

- Features: SF, scope type, product complexity, building access factors
- Learn the SF-to-man-day ratio per scope type
- Handle non-linear relationships (setup time is fixed, production scales with SF)

**Phase 3 Deliverable:** Cost estimation API: input (scope type, product, SF, project type) -> output (predicted cost/SF, markup%, man-days, total estimate with confidence interval).

---

## Phase 4: Plan Reading with Vision AI (Week 4-6)

**Goal:** Extract room areas, ceiling types, and scope suggestions from architectural drawings.

### 4.1: Claude Vision API Integration

Set up the pipeline for sending architectural drawings to Claude Vision.

- PDF-to-image conversion at appropriate DPI (300 DPI for detail)
- Multi-page handling (floor plans are typically multi-sheet sets)
- Prompt engineering for architectural drawing interpretation
- Structured output parsing (rooms, areas, annotations)

### 4.2: Room/Area Extraction from Floor Plans

Identify and extract individual rooms and spaces from floor plans.

- Room name/number extraction from text labels
- Room boundary detection (conceptual, not pixel-perfect)
- Room grouping by floor and building
- Handle open plan areas and corridors

### 4.3: Ceiling Type and Height Detection

Extract ceiling specifications from reflected ceiling plans (RCPs).

- Ceiling type annotations (ACT, GWB, exposed structure, etc.)
- Ceiling height notations
- Grid layout patterns (2x2, 2x4)
- Special ceiling features (clouds, baffles, soffits)

### 4.4: Wall Treatment Area Calculation

Estimate wall panel and fabric wall areas from plans and elevations.

- Wall panel locations from interior elevations
- Panel height and width extraction
- Running linear footage for wainscot and chair rail applications

### 4.5: SF Estimation from Plan Dimensions

Calculate square footages from dimensional information in drawings.

- Read dimension strings from plans
- Calculate room areas from boundary dimensions
- Handle irregular shapes (L-shaped rooms, curved walls)
- Cross-reference with room schedules if present

### 4.6: Scope Type Suggestion from Drawing Annotations

Use drawing annotations, keynotes, and specifications to suggest scope types.

- Match ceiling type annotations to ACT scope types
- Identify wall treatment keynotes
- Reference specification section numbers (09 51 00 = ACT, 09 84 30 = sound masking)
- Output suggested scope tag and product for each room/area

**Phase 4 Deliverable:** Upload a PDF plan set and receive a structured room-by-room breakdown with SF estimates, suggested ceiling/wall types, and scope tags. Manual review and correction UI.

---

## Phase 5: Estimation Engine (Week 6-7)

**Goal:** Combine plan reading output with cost models to produce complete estimates.

### 5.1: Plan-to-Estimate Pipeline

Orchestrate the full flow from uploaded plans to generated estimate.

- Accept plan reading output (rooms, SFs, suggested scope types)
- Map each room's scope suggestions to the cost model
- Generate scope-level estimates (cost/SF, markup, man-days, total)
- Aggregate into a project-level estimate

### 5.2: Auto-Generate Buildups

Produce Excel buildups matching the existing format.

- Generate Format B (multi-scope with tags) as the default output
- Populate all fields: tag, description, SF, cost/SF, material cost, markup, material price, man-days, labor price, sales tax, total
- Include grand total and summary section
- Match existing Excel formatting (fonts, column widths, number formats)

### 5.3: Confidence Scoring

Quantify how confident the system is in each estimate component.

- Model prediction confidence (based on training data density near the input)
- Plan reading confidence (how clearly the plans were read)
- Overall estimate confidence (combined score)
- Flag low-confidence items for manual review

### 5.4: Comparison with Similar Historical Projects

Find and display the most similar historical projects for validation.

- Feature-based similarity search (scope types, SFs, project type)
- Display comparable project costs side-by-side
- Highlight where the estimate differs significantly from comparables
- Allow users to anchor to a specific comparable

### 5.5: Export to Excel

Export estimates in the standard buildup format.

- Exact match to existing Excel buildup format
- Optionally include comparable project data on a separate sheet
- Include metadata (estimate date, confidence, source plans)

**Phase 5 Deliverable:** End-to-end pipeline: upload architectural plans -> receive a complete buildup estimate with confidence scores and historical comparisons, exported to Excel.

---

## Phase 6: Web Application (Week 7-9)

**Goal:** Build a user-friendly web interface for the estimation engine.

### 6.1: FastAPI Backend

RESTful API serving the estimation engine.

- `POST /api/estimates` — Create new estimate from uploaded plans
- `GET /api/estimates/{id}` — Retrieve estimate with all scopes
- `PATCH /api/estimates/{id}/scopes/{scope_id}` — Adjust individual scope
- `GET /api/projects` — Browse historical projects
- `GET /api/projects/{id}` — Project detail with all scopes and documents
- `POST /api/estimates/{id}/export` — Export to Excel
- `POST /api/estimates/{id}/quote` — Generate quote PDF
- Authentication via API keys (internal tool, simple auth)

### 6.2: Next.js Frontend

Modern web interface for the estimation workflow.

- Upload interface (drag-and-drop PDF plans)
- Processing status with real-time progress
- Estimate review and adjustment UI
- Historical project browser with search and filters

### 6.3: Project Dashboard

Browse and search the historical project database.

- Project list with filters (scope type, date range, project type, GC)
- Project detail view (scopes, costs, documents, vendor quotes)
- Cost trend charts (cost/SF over time by scope type)
- Vendor pricing trends

### 6.4: Estimate Builder UI

Interactive estimate editing interface.

- Table-based scope editor (add, remove, modify scopes)
- AI suggestions with accept/reject/modify workflow
- Real-time total recalculation
- Side-by-side comparison with historical projects
- Notes and annotations per scope

### 6.5: Quote Generation

Generate customer-facing quotes from estimates.

- Match existing T-004B template format
- Auto-populate from estimate data
- Editable fields (payment terms, exclusions, custom notes)
- PDF export with professional formatting
- Sequential quote number assignment

### 6.6: User Authentication and Roles

Simple role-based access control.

- Admin: full access, model retraining, system config
- Estimator: create/edit estimates, generate quotes
- Viewer: read-only access to projects and estimates

**Phase 6 Deliverable:** Working web application accessible to Commercial Acoustics staff. Full workflow: upload plans -> review AI estimate -> adjust -> generate quote -> export.

---

## Phase 7: Continuous Learning (Ongoing)

**Goal:** Build feedback loops that improve the system over time.

### 7.1: Actual vs. Estimated Cost Feedback

Track how estimates compare to actual project outcomes.

- Input actual costs after project completion
- Calculate estimate accuracy metrics (MAPE, bias)
- Identify systematic over/under-estimation patterns
- Dashboard showing accuracy trends

### 7.2: Model Retraining Pipeline

Automated model updates as new data accumulates.

- Scheduled retraining (monthly or after N new projects)
- A/B comparison of new model vs. current model
- Automated rollback if new model performs worse
- Model versioning and performance history

### 7.3: Vendor Price Tracking and Updates

Keep vendor pricing current.

- Track vendor quote prices over time
- Alert when material costs change significantly
- Automatically update cost/SF baselines when vendor prices shift
- Integrate vendor price lists if available electronically

### 7.4: New Product and Scope Type Handling

Extend the system to handle new products and scope types as they emerge.

- Detect unknown product names during extraction
- Workflow to add new products to the catalog
- Handle new scope types (e.g., if CA starts doing acoustic flooring)
- Model adaptation for new categories with limited data

**Phase 7 Deliverable:** Self-improving estimation system that gets more accurate with every completed project.

---

## Timeline Summary

| Phase | Duration | Key Output |
|-------|----------|-----------|
| Phase 0 | Current | Documentation, schema, project setup |
| Phase 1 | Week 1-2 | All 500+ projects extracted into database |
| Phase 2 | Week 2-3 | Clean, normalized, model-ready dataset |
| Phase 3 | Week 3-4 | Working parametric cost models |
| Phase 4 | Week 4-6 | AI plan reading from architectural drawings |
| Phase 5 | Week 6-7 | End-to-end estimation engine |
| Phase 6 | Week 7-9 | Web application for internal use |
| Phase 7 | Ongoing | Continuous learning and improvement |

**Total to MVP (Phase 5):** ~7 weeks
**Total to Production App (Phase 6):** ~9 weeks

---

## Risk Factors

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Excel formats more varied than expected | Phase 1 delay | Use Claude API for flexible extraction; manual fallback queue |
| Insufficient training data per scope type | Phase 3 accuracy | Bayesian priors from domain knowledge; transfer learning across scope types |
| Plan reading accuracy too low | Phase 4 unusable | Start with simple plans; manual SF input as fallback |
| Claude API costs exceed budget | Ongoing expense | Cache extraction results; batch processing; use Haiku for simple tasks |
| Product name normalization mismatches | Data quality | Manual review queue; conservative matching thresholds |
