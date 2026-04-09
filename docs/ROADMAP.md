# Acoustimator Development Roadmap

Phased development plan for the Acoustimator estimation engine. Each phase builds on the previous, with clear deliverables and acceptance criteria.

**Status key:** ✅ Complete · 🔄 In progress · ⚠️ Code written, not run · ❌ Not started

---

## Phase 0: Project Setup & Documentation

**Goal:** Establish the project foundation — repository, documentation, analysis, and development environment.

### Tasks
- ✅ Initialize Git repository (`main` branch, remote on GitHub)
- ✅ Deep analysis of the 500+ project dataset (see [ANALYSIS.md](ANALYSIS.md))
- ✅ Define database schema (see [DATA_SCHEMA.md](DATA_SCHEMA.md))
- ✅ Document tech stack and architecture decisions (see [TECH_STACK.md](TECH_STACK.md))
- ✅ Define repository structure (see [REPO_STRUCTURE.md](REPO_STRUCTURE.md))
- ✅ Create `pyproject.toml` with all required dependencies
- ✅ Create `.env.example` with required environment variables
- ✅ Set up `.gitignore` (data/, models/, .env, etc.)
- ✅ Create `CLAUDE.md` project instructions
- ✅ Validate Dropbox data source accessibility (134 buildups found and processed)
- ✅ Set up Neon project — `dev` branch provisioned and connected
- ✅ Configure Vercel project — linked to `acoustimator` under Commercial Acoustics team
- ❌ Set up Neon↔Vercel integration for auto-branch preview databases
- ❌ Configure Vercel environment variables (DATABASE_URL, ANTHROPIC_API_KEY)

**Deliverable:** Fully documented project ready for development.

---

## Phase 1: Data Extraction Pipeline

**Goal:** Extract structured data from all historical project folders into a normalized database.

### 1.1: Excel Buildup Parser ✅ COMPLETE

**What was built:** `src/extraction/excel_parser.py` — uses openpyxl to read cell grids, sends structured data to Claude Sonnet for intelligent field extraction, returns validated Pydantic models. Handles all four format types (A/B/C/D).

**Results:**
- 126 buildups processed from 134 source files (some folders had multiple xlsx variants → upserted to same project)
- 124 projects, 326 scopes loaded into Neon dev branch
- 223 additional cost items extracted (lift rental, travel, equipment, consumables, commission, punch list, site visit, setup/unload, P&P bond, go-back, other)
- 245 unit tests passing

**Acceptance criteria met:**
- ✅ 124/134 folders successfully extracted (93%, above 90% target)
- ✅ All 4 format types handled
- ✅ Extraction totals within 2% verified via field-level extraction

**Key files:**
- `src/extraction/excel_parser.py` — core parser
- `scripts/extract_all.py` — batch runner with `--skip-existing`, `--dry-run`, `--concurrency`
- `scripts/load_to_db.py` — loads extracted JSON → Neon

---

### 1.2: Quote PDF Parser ✅ COMPLETE

**What was built:** `src/extraction/pdf_parser.py` — PyMuPDF-based parser for T-004A/B/E quote templates. Four-strategy grand total extraction handles multi-line column layouts PyMuPDF produces from CA quote PDFs. Confidence scoring by field presence.

**Results (608 PDFs scanned from +ITBs):**
- 606/608 successfully parsed (99.7%) — 2 failures are image-only scans
- Quote number extracted: **99.7%** (target: ≥95%) ✅
- Grand total extracted: **98.4%** (target: ≥95%) ✅
- JSON output: `data/extracted/quotes/` (606 files)

**Notes:**
- Line item extraction is partial — PyMuPDF column linearization makes table parsing unreliable; this is a future improvement
- 10 missing grand totals are genuinely unusual (typo like `$19.104.59`, non-standard labels)

**Key files:**
- `src/extraction/pdf_parser.py` — core parser
- `scripts/parse_quotes.py` — batch runner

---

### 1.3: Vendor Quote Parser ✅ COMPLETE

**What was built:** `src/extraction/vendor_parser.py` — two-pass extraction: PyMuPDF text first, Claude Vision fallback (triggered when text extraction confidence < 0.4). Maps vendor name patterns to 14 canonical vendors.

**Results (full 192-file run):**
- 192/192 vendor quotes extracted (100%)
- All PDFs used Vision path — vendor quote PDFs are scanned/image-heavy
- Confidence scores 0.88–0.97
- 192 vendor quotes loaded to DB, 35 unique vendors created
- 16 quotes with NULL project_id (folder name mismatches like `+DD Dynasty` vs `+Dynasty DD`)

**Acceptance criteria met:**
- ✅ Extract vendor and total from 80%+ of vendor quotes — achieved 100%
- ✅ Line-item extraction for top 5 vendors (SKU, product, qty, unit, unit_cost all extracted)

**Key files:**
- `src/extraction/vendor_parser.py` — core parser
- `scripts/parse_vendor_quotes.py` — batch runner with `--dry-run`, `--limit`, `--skip-existing`

---

### 1.4: Data Validation and Quality Checks ✅ COMPLETE

**What was built:**
- `src/extraction/validator.py` — math consistency checks (total ≈ material + labor + tax, 2% tolerance), outlier detection per scope type
- `scripts/validate_extraction.py` — CLI that checks extracted JSONs against known audit values (bug fixed: `format_type` lookup now correctly descends into `project` key)

**Results (126-project full run):**

| Metric | Value |
|---|---|
| Files validated | 126/126 (100%) ✅ |
| Fully valid projects | 89 (70.6%) |
| Projects with issues | 37 (29.4%) |
| Valid scopes | 289/340 (85%) |

**Top issues found:**
- 45 scopes missing SF — validator's `area_types` set too broad; AP/RPG scopes are unit-priced, not SF-based (needs validator fix in Phase 2)
- 7 scopes with markup >100% across 4 projects (USF NTA Bldg, St Thomas, VCA, USF MUS) — likely extraction errors where model confused multiplier with percentage
- Math mismatch warnings (48 total/94 material): expected from scrap rates and rounding

**Known audit cases:**
- Grant Thornton: extracted 4,700 SF vs. known-good 4,200 SF (11.9% off) — real extraction error
- Baycare Dunedin Mease, HCA Gainesville, BMG 231: all PASS

**Acceptance criteria met:** ✅ Validation report generated for 100% of extracted projects.

---

### 1.5: Load into Database ✅ COMPLETE

**Results:** All extracted data persisted in Neon PostgreSQL `dev` branch.
- 124 projects (one row per unique `folder_name`)
- 326 scopes across all projects
- 223 additional cost items (all 12 cost types present)
- 253 extraction run audit records

**Key files:** `scripts/load_to_db.py`, `src/db/loader.py`, `alembic/versions/001_initial_schema.py`

---

### 1.6: Non-Standard Line Item Extraction ✅ COMPLETE

All 12 additional cost types detected and loaded:

| Type | Count |
|------|-------|
| other | 64 |
| travel_per_diem | 34 |
| equipment | 25 |
| travel_hotels | 21 |
| travel_flights | 19 |
| consumables | 19 |
| lift_rental | 11 |
| commission | 9 |
| punch_list | 7 |
| site_visit | 6 |
| setup_unload | 6 |
| bond | 2 |

**Phase 1 Deliverable:** Excel extraction pipeline complete. Quote PDF parser at 99.7%/98.4%. Vendor quote parser tested at 100% (full 192-file run in progress). All data loaded to Neon.

---

## Phase 2: Data Enrichment & Cleaning

**Goal:** Transform raw extracted data into a clean, normalized dataset ready for modeling.

### 2.1: Product Name Normalization ✅ COMPLETE

**Results:**
- Catalog expanded: 30 → **74 products** (147% increase)
- Match rate: 24.4% → **78.5%** (244/311 scopes matched)
- Remaining 67 unmatched: compound multi-product names (`&`/`+`/`;` separators) and project area labels accidentally extracted as product names — not matchable without normalizer code changes

**New products added (44):** Lencore Spektrum, Vektor Gold/iNet/Silver, Arktura Atmosphera/Softspan, Armstrong Ultima/Healthzone/Calla/MetalWorks/Axiom/Feltworks, USG Lyra/Ceramaguard/ClimaPlus, Rockfon family, MDC Embossed, Koroseal Panawall, Camira/Wolf Gordon/Burch fabrics, AkuPanel, FilzFelt, Kirei Echopanel, Pinta Willtec, 3Form Hush, Autex, Tectum, MBI Spectrum, ASI Microperf, American Tin Ceilings, generic catchalls, and more.

**Key files:** `data/products_catalog.json`, `scripts/normalize_products.py`

---

### 2.2: Scope Type Classification ✅ COMPLETE

**Results:** 64 scopes reclassified, AP type fully eliminated.

| Reclassified To | Count | Examples |
|-----------------|-------|---------|
| AWP | 30 | Generic acoustic panels, AkuPanel, Acoufelt, Silver Papier, Felt Panels |
| Baffles | 15 | Clouds (Acoustic, CSI, J2, Zintra), FilzFelt AroPlank, Feltworks Blades, Rockfon Island |
| ACT | 8 | Axiom trim, MBI Spectrum, MetalWorks, Tin Ceilings, Soniguard |
| FW | 7 | Fabric+track scopes, Wolf Gordon Gather, yardage-priced walls |
| RPG | 2 | Convex/Concave diffusers |
| SM | 2 | Speaker systems |

**Final distribution:** ACT:159 · AWP:57 · SM:31 · Baffles:30 · FW:25 · WW:12 · RPG:6 · Other:6

**6 remaining Other:** R-19 Insulation, Pipe Grid, Unistrut (non-acoustic construction materials) + 3 null-name scopes — correctly left as Other.

**Validator fix:** `src/extraction/validator.py` — removed `AP` from `area_types`, added `is_unit_priced` guard so RPG/Axiom/trim scopes priced per-piece or per-LF don't incorrectly trigger "missing SF" errors.

**Key files:** `scripts/reclassify_scopes.py`, `src/extraction/validator.py`

---

### 2.3: Historical Price Indexing ✅ COMPLETE (⚠️ dates need fix)

**What was built:**
- `scripts/price_index.py` — full cost/SF trend analysis by scope type vs. ANALYSIS.md benchmarks, outlier detection, labor normalization
- `src/enrichment/price_indexer.py` — `PriceIndex` class for Phase 3 ML: `normalize_labor()`, `normalize_scope()`, `cost_features()`, `to_training_records()`
- `data/extracted/price_index.json` — 125KB output with per-scope normalized records + aggregates

**Key findings:**
- **⚠️ Quote dates NULL in DB** — extraction captures dates but loader doesn't persist them to `projects.quote_date`. True time-series blocked until fixed (tracked below in Bugs).
- Labor rate normalization: bulk of projects are 2023–2024 era ($504–$540/day); normalizing to current $725/day requires +37–41% uplift per scope type
- Cost/SF vs. benchmarks: ACT median $3.45 on-target; WW $35.69 within range; AWP only 4 rows with cost_per_sf (too sparse); SM has zero cost_per_sf (install-only pricing)
- Armstrong grid prices rose 25-30% Aug→Oct 2025 (detected via vendor quotes)
- 20 ACT outliers flagged: "Hurricane Phase 2" at $31/SF (custom metalwork), Wellen Park at $0.80/SF (partial scope)

---

### 2.4: Vendor Cost Tracking ✅ COMPLETE

**Results:**
- 192/192 vendor quotes loaded to DB, 35 unique vendors created
- 16 quotes with NULL project_id (folder name mismatches like `+DD Dynasty` vs. `+Dynasty DD`)
- `vendor_quotes.project_id` made nullable (DB schema updated, `src/db/models.py` updated)

**Key findings:**
- Top material vendors: Armstrong World Industries (avg $152K/quote), Koroseal ($155K), GMS Southeast/GatorGyp ($111K), FBM ($69K)
- CA's own outgoing quotes (T-004A/B/E) were included in extraction — avg $99K, 107 quotes
- **Armstrong grid price alert:** Prelude XL tees and main beams +25-30% Aug→Oct 2025
- GMS Southeast (GatorGyp) = dominant ACT/grid supplier; MDC = top wall fabric vendor

**Key files:**
- `scripts/load_vendor_quotes.py` — loads 192 JSONs → DB
- `src/enrichment/vendor_tracker.py` — `VendorCostTracker` class with `get_price_history()`, `get_vendor_summary()`, `detect_price_changes()`

---

### 2.5: Data Quality Dashboard ✅ COMPLETE

**Key files:** `scripts/quality_report.py`, `data/extracted/quality_report.txt`

**Live DB snapshot (post-Phase 2):**

| Metric | Value |
|--------|-------|
| Projects | 124 |
| Scopes | 326 (post-reclassification: ACT:159, AWP:57, SM:31, Baffles:30, FW:25, WW:12, RPG:6, Other:6) |
| Products in catalog | 74 |
| Scopes with product_id linked | 78.5% |
| cost_per_sf populated | 58.9% (192 missing — SM and unit-priced scopes) |
| product_name populated | 95.4% |
| Vendor quotes loaded | 192 (35 vendors) |
| Quote PDFs extracted | 606 (99.7% with quote number) |

**ML Readiness (all required features: scope_type + cost_per_sf + square_footage + markup_pct):**
- ACT: **90 complete rows** — ✅ READY TO TRAIN
- AWP: ~20-25 complete rows — borderline
- Baffles: ~12 complete rows — use LOOCV or pool with AWP
- SM/FW/WW/RPG: insufficient for standalone models — use general model

**Phase 2 Deliverable:** ✅ Clean, normalized dataset with 74 canonical products (78.5% scope coverage), reclassified scope types, labor-normalized price index, 192 vendor quotes in DB, and a full quality dashboard. ACT scope type ready for ML training.

**Known bug to fix before Phase 3:** Quote dates not persisted to `projects.quote_date` — loader needs to map `extraction_result.project.quote_date` → DB. Fix in `src/db/loader.py`.

---

## Phase 3: Parametric Cost Model

**Goal:** Train ML models that predict cost components from project parameters.

*Prerequisites: Phase 2 complete (clean, classified, normalized data)*

### 3.1: Feature Engineering ✅ COMPLETE

**Files:** `src/models/features.py` (`FeatureEngineer` class), `data/models/training_data.csv` (326 rows, 23 features)

**Engineered features:**
- `log_square_footage` — log1p(SF), normalizes skewed distribution
- `scope_type_encoded` — label-encoded canonical type
- `material_cost_per_sf` — strongest predictor (0.46–0.93 importance across models)
- `man_days_per_sf` — second most important
- `labor_rate_normalized` — daily_labor_rate / 725 (normalizes to current rate)
- `project_scope_count` — project complexity proxy
- `product_tier` — 0/1/2/3 (economy → specialty) from product name keywords
- `is_healthcare`, `is_education`, `is_church` — project type flags from name/GC keywords

**Note:** `project_type` is NULL across all 124 projects — a significant missing signal for Phase 3 accuracy. Workaround: infer from project/GC name keywords.

---

### 3.2 + 3.3: Train Cost Models + Validation ✅ COMPLETE

**Files:** `src/models/cost_model.py`, `scripts/train_models.py`, `data/models/model_manifest.json`

**Target variable:** `cost_per_sf_total` = total_price / square_footage (full quoted price per SF)

| Scope | Algorithm | n_train | Test MAPE | R² | Target | Status |
|-------|-----------|---------|-----------|-----|--------|--------|
| ACT | RandomForest | 82 | **13.5%** | 0.952 | ≤15% | ✅ MET |
| AWP | RandomForest | 11 | **18.4%** | 0.194 | ≤20% | ✅ MET |
| FW | RandomForest | 13 | **21.0%** | 0.083 | ≤25% | ✅ MET |
| AP | RandomForest | 8 | 66.8% | 0.531 | ≤25% | ❌ too few rows |
| GENERAL | RandomForest | 132 | 27.0% | 0.709 | ≤25% | ❌ mixes scope types |
| Baffles | — | — | skipped | — | — | only 6 rows |
| WW | — | — | skipped | — | — | only 8 rows |

**Key insight:** `material_cost_per_sf` is dominant (46–93% importance), confirming material cost drives total price. Use ACT model for production, GENERAL as fallback for unknown types. AP/Baffles/WW/RPG need more data before standalone models are viable.

**Saved models:** `data/models/ACT_cost_model.joblib`, `AWP_cost_model.joblib`, `FW_cost_model.joblib`, `general_cost_model.joblib`

---

### 3.4: Markup Prediction Model ✅ COMPLETE

**Files:** `src/models/markup_model.py`, `scripts/train_markup_model.py`, `data/models/markup_model.joblib`

**Results:** Test MAPE 16.0%, R²=0.362 (CV R²=0.006 ± 0.164 — markup variance is inherently high)

**Per-type mean predictions vs actuals:** ACT ~33%, FW ~53%, WW ~38%, AWP ~41% — all directionally correct and within business ranges.

**Top features:** log_square_footage (42%), scope_type_encoded (20%), labor_rate_normalized (17%), project_scope_count (14%)

**Limitation:** `project_type` is NULL for all projects — adding healthcare/education/GC-vs-direct context would significantly improve this model.

---

### 3.5: Labor Estimation Model ✅ COMPLETE

**Files:** `src/models/labor_model.py`, `scripts/train_labor_model.py`, `data/models/labor_model.joblib`

**Discovered scaling law:** `man_days ≈ 0.36 × SF^0.49` — square-root scaling (larger jobs get more efficient, setup overhead embedded in scope-type constant)

**Results:** CV MAPE 66% ± 13% (expected — two identical-SF scopes can differ 2-3× from site/crew/height factors not in schema). CV R²=0.578 on log scale.

**Sample predictions (at current $725/day):**
- ACT 1,000 SF → 6.5 days · ACT 5,000 SF → 22 days · ACT 30,000 SF → 44 days
- AWP 2,000 SF → 14 days · FW 1,500 SF → 12 days · WW 2,000 SF → 19 days

**Top feature:** log_square_footage (62.6% importance) confirms SF drives labor more than any other factor.

**Phase 3 Deliverable:** ✅ Cost estimation API operational: input (scope_type, product, SF) → output (predicted cost/SF, markup%, man-days, total with confidence interval). Three model classes ready: `CostModel`, `MarkupModel`, `LaborModel` in `src/models/`.

---

## Phase 4: Plan Reading — Text Extraction + Vision AI ✅ COMPLETE

**Goal:** Extract room areas, ceiling types, and scope suggestions from architectural drawings.

### 4.1: PyMuPDF Text + Annotation Extraction (PRIMARY) ✅ COMPLETE

**What was built:** `src/extraction/plan_parser/text_extractor.py` + `page_classifier.py`
- Full PyMuPDF text extraction from vector PDF layers
- Bluebeam polygon annotation parsing — reads pre-calculated area values ("Area: 609.87 sq ft") directly from annotation content
- Page classification: vector-rich (text length > 50 chars) vs. raster
- Page type detection from keywords: rcp, floor_plan, elevation, schedule, cover, unknown

### 4.2: Claude Vision API Integration (SUPPLEMENTARY) ✅ COMPLETE

**What was built:** `src/extraction/plan_parser/vision_extractor.py`
- PDF page → PNG at 150 DPI via PyMuPDF
- Async Claude Vision call with structured JSON response (rooms, ceiling_specs, notes)
- Capped at 5 raster pages per drawing (cost control)
- Hybrid: text first, Vision only for raster pages

### 4.3: Room/Area Extraction ✅ COMPLETE

**What was built:** `src/extraction/plan_parser/room_extractor.py` — 5 detection passes:
1. ROOM header ("ROOM 101 - CONFERENCE ROOM")
2. Number-dash-name lines ("101 - Conference Room")
3. Finish schedule tables (multi-column room/finish grid)
4. Open-plan areas (LOBBY, RECEPTION, OPEN OFFICE)
5. Bluebeam annotation labels with scope tags

### 4.4: Ceiling Type and Height Detection ✅ COMPLETE

**What was built:** `src/extraction/plan_parser/ceiling_extractor.py`
- Detects ACT, GWB, Exposed Structure, Baffles, FW, WW, SM ceiling types
- Grid pattern normalization: "24X48" → "2x4", "24X24" → "2x2"
- Product spec extraction near ceiling type annotations
- Scope tag linking (ACT-1, ACT-2, etc.)

### 4.5: Wall Treatment Area Calculation ✅ COMPLETE

**What was built:** `src/extraction/plan_parser/wall_extractor.py` — 4 detection passes:
- Bluebeam AWP/FW polygon annotations (highest confidence)
- Treatment label + area text: "FABRIC WALL - 450 SF"
- Scope tag scanning with surrounding-context SF lookup
- Wainscot/chair rail: linear footage + height in decimal feet

### 4.6: SF Estimation from Plan Dimensions ✅ COMPLETE

**What was built:** `src/extraction/plan_parser/sf_estimator.py` — 3-tier strategy:
1. Bluebeam polygon annotations (confidence 0.95) — pre-calculated, most reliable
2. Explicit SF labels in text: "2,450 SF", "2,450 SQ FT"
3. Dimension pair parsing: `12'-6" × 18'-0"` room pairs

**Validation:** Seven Pines Jax Takeoff Dwgs → 1,595.38 SF (matches known-good)

### 4.7: Scope Type Suggestion from Annotations ✅ COMPLETE

**What was built:** `src/extraction/plan_parser/scope_suggester.py` — 6-priority system:
1. Bluebeam polygon with explicit scope tag ("ACT-1 - 2,450 SF") → conf 0.95
2. Ceiling spec with explicit scope_tag → conf 0.85
3. Room ceiling_type inference → conf 0.75
4. Bluebeam color hint (Red=ACT, Blue=AWP, Green=FW) → conf 0.70
5. Spec section numbers (09 51 = ACT, 09 84 = SM) → conf 0.65
6. Keyword scan in text → conf 0.50

Auto-numbering, deduplication (merge same tag, sum areas, union rooms), yellow deduct correctly suppressed.

### 4.8: Batch Extraction ✅ COMPLETE

**Results (full corpus run):**
- **331 drawing PDFs** discovered across 127 project folders
- **328/328 processed** (3 skipped — already extracted), **0 failures**, 100% success rate
- **8,493 total scope suggestions** generated
- **5.4 million SF** of acoustic work identified
- **196 seconds** total (~0.6s/file, no Vision API)
- Output: `data/extracted/plans/{project_folder}/{filename}.json`

**Key files:**
- `src/extraction/plan_parser/` — full package (9 modules)
- `src/extraction/plan_reader.py` — top-level orchestrator
- `scripts/read_plans.py` — batch runner (`--dry-run`, `--single`, `--limit`, `--project`, `--skip-existing`)

**Phase 4 Deliverable:** ✅ Upload a plan set → receive room-by-room breakdown with SF estimates, scope tags, and product suggestions. Full corpus of 331 drawings extracted.

---

## Phase 5: Estimation Engine

**Goal:** Combine plan reading output with cost models to produce complete estimates.

### 5.1: Plan-to-Estimate Pipeline ✅ COMPLETE

**What was built:** `src/estimation/estimator.py` — `estimate_from_plan_result(plan_result) → ProjectEstimate`
- Routes each scope suggestion to the right cost model (ACT/AWP/FW/general)
- Lazy-loads `.joblib` model files, heuristic fallbacks if missing
- Financial formula: material_cost × (1 + markup) + labor + tax
- Comparable project lookup from training CSV
- Filters scopes with confidence < 0.3 or no area_sf

**Validation (Seven Pines Jax — 1,595 SF):** 3 AWP scopes → **$68,677 total, 15.8 man-days**, 🟢 High (93%)

### 5.2: Auto-Generate Buildups ✅ COMPLETE

**What was built:** `src/estimation/excel_writer.py` — `write_estimate_to_excel() → Path`
- Format B layout: project header, column headers, per-scope sections with Excel formulas
- Yellow scope header rows, gray column header, bold grand total (14pt)
- Notes sheet: warnings, per-scope confidence, comparables
- Handles None fields gracefully; empty-estimate notice if no scopes

### 5.3: Confidence Scoring ✅ COMPLETE

**What was built:** `src/estimation/confidence.py`
- `compute_scope_confidence()` — 0.6 × plan_confidence + 0.4 × model_accuracy (ACT=0.87, AWP=0.82, FW=0.79, general=0.73), OOD SF penalty
- `compute_project_confidence()` — area-weighted model score, 6 flag conditions, level-gated recommendations
- `format_confidence_badge()` — "🟢 High (93%)", "🟡 Medium (61%)", "🔴 Low (34%)"

### 5.4: Historical Project Comparison ✅ COMPLETE

**What was built:** `src/estimation/comparator.py`
- `find_comparable_projects(session, scope_type, area_sf, cost_per_sf, top_n=3)` — async DB query
- Weighted similarity: scope_type match (0.5) + log-ratio SF distance (0.3) + cost proximity (0.2)
- `find_comparables_sync()` wrapper for non-async contexts

### 5.5: Export to Excel ✅ COMPLETE

Covered by 5.2 above. Format B/C match with optional Notes sheet.

### 5.6: Batch Estimation Runner ✅ COMPLETE

**What was built:** `scripts/estimate_from_plans.py`
- Reads 329 plan JSONs from `data/extracted/plans/`
- `--export-excel`, `--project`, `--limit`, `--dry-run`, `--skip-existing`
- Prints per-file status with confidence badge and dollar total

**Phase 5 Deliverable:** ✅ Upload plans → complete buildup estimate with confidence scores and historical comparisons, exported to Excel. 357 tests passing.

---

## Phase 5.5: GitHub Architecture & CI/CD ✅ COMPLETE

**Goal:** Establish professional GitHub workflow before Phase 6 brings external contributors and production deployments. All future code arrives via PRs with automated checks and optional agent code review.

### 5.5.1: GitHub Actions CI Pipeline ✅

- **`.github/workflows/ci.yml`** — lint + ruff format + pytest (Python 3.12) on all PRs and pushes to `main`
- **`.github/workflows/claude-review.yml`** — Claude Code reviews every PR diff, posts inline comments
- Concurrency: cancel in-progress runs on same PR branch

### 5.5.2: Agent Code Review ✅

- CodeRabbit + Claude Code Action both configured and active on all PRs

### 5.5.3: Branch Protection & PR Policy ✅

- `main` branch: CI required to pass; all code via feature branches (`feat/`, `fix/`, etc.)
- Vercel preview deployments auto-created on every PR

### 5.5.4–5.5.6: Pre-commit Hooks / Dependabot / Initial PR ⚠️ Deferred

- Pre-commit hooks and Dependabot not yet configured (low priority)
- Phase 1–5 already merged to `main` via PR #7 (clean cherry-pick branch)

**Phase 5.5 Deliverable:** ✅ CI pipeline running, Claude PR review active, `main` is always green.

---

## Phase 6: Web Application

**Goal:** Build a user-friendly web interface for the estimation engine.

### 6.1: FastAPI Backend ✅ COMPLETE

All endpoints built, tested, and running locally (Vercel deployment pending env var config):

- `POST /api/estimates` — Create estimate from uploaded plans
- `GET /api/estimates` — List estimates (paginated, status-filterable)
- `GET /api/estimates/{id}` — Retrieve estimate with scopes + comparables
- `PATCH /api/estimates/{id}/scopes/{scope_id}` — Adjust scope fields inline
- `GET /api/projects` — Browse historical projects (paginated, filterable)
- `GET /api/stats/cost-trends` — Aggregate cost/SF by year + scope type
- `POST /api/estimates/{id}/export` — StreamingResponse Excel (.xlsx) buildup
- `POST /api/estimates/{id}/quote` — Quote PDF (reportlab-generated, sequential CA-YYYY-NNNN numbering)

**Additional infrastructure (post-PR merge):**
- `src/api/middleware/api_key.py` — `ApiKeyMiddleware` (dev-safe X-API-Key header check)
- CORS fixed for `http://localhost:4000` dev server
- `src/db/migrations/add_quotes_table.sql` — `quotes` table migrated to Neon dev branch
- Bug fix: `cast(str)` → `cast(String)` in `stats.py` and `projects.py` (SQLAlchemy requires `String` type, not Python `str`)

**Key files:** `src/api/main.py`, `src/api/routes/estimates.py`, `src/api/routes/projects.py`, `src/api/routes/stats.py`, `api/index.py` (Vercel entrypoint)

**Note:** ML model imports wrapped in `try/except ImportError` so API starts on Vercel without sklearn (model `.joblib` files are gitignored). Vercel slim `api/requirements.txt` excludes sklearn/scipy/xgboost.

### 6.2: Next.js Frontend ✅ COMPLETE

Full CA brand theme + real API wiring (PRs #8, #10):
- Space Grotesk + JetBrains Mono fonts, CA green `#a1d67c` sole accent
- `#080b10` → `#0e1219` → `#131822` dark surface layers, translucent borders
- `frontend/src/lib/api.ts` — typed client with field mapping from API wire format → frontend types
- Frontend runs on `:4000`, backend on `:8000` (CORS configured for both)

**Pages:** Dashboard, `/estimates` (new), New Estimate wizard, Estimate detail, Projects browser — all wired to real API via `useEffect` + `useState`. Mock data fully replaced.
**Components:** StatCard, CostTrendChart, ConfidenceBadge, ScopeTypeBadge, EstimateTable (inline-editable, PATCH wired), EstimateSummary, ComparableProjects, PlanUploadZone

### 6.3: Project Dashboard ✅ COMPLETE

- Stat cards (hardcoded totals — ⚠️ TODO: add DB aggregate endpoint for live counts)
- Cost/SF trend chart driven by real `GET /api/stats/cost-trends` (⚠️ returns empty until `quote_date` loader bug is fixed — see Phase 2.3)
- Recent estimates table + **Kanban board toggle**
- Table/board toggle: ≡ table view, ⊞ board view
- Board groups by status: Draft → Reviewed → Finalized → Exported

### 6.4: Estimate Builder UI ✅ COMPLETE

- Inline-editable scope table wired to `PATCH /api/estimates/{id}/scopes/{scope_id}`
- Accept/Unaccept per scope row
- Confidence badges with glow dot
- Comparable projects sidebar panel (enriched from DB)
- AI model notes card
- Sticky export bar — Export fires `POST /api/estimates/{id}/export` (blob download)

### 6.4.1: Kanban Board ✅ COMPLETE (PR #12)

- `EstimateCard.tsx`, `BoardColumn.tsx`, `EstimateBoard.tsx` — 4-column static Kanban
- `/estimates` page — full estimates list with status filter + board/table toggle
- Dashboard: Recent Estimates has table/board toggle
- Sidebar: "Estimates" nav link added
- Accent colors: Draft=slate, Reviewed=blue, Finalized=CA green, Exported=purple

### 6.4.2: PWA + Responsive Design ✅ COMPLETE (PR #11)

- `public/manifest.json` — installable PWA (standalone, CA green theme-color)
- `public/icons/` — app icons (SVG + PNG)
- `layout.tsx` — appleWebApp, viewport meta, manifest link
- `Sidebar.tsx` — mobile drawer with slide transition + tap-to-close overlay
- `MobileHeader.tsx` — 48px top bar (hamburger + wordmark) for mobile
- Responsive: 2-col stat cards on mobile, `overflow-x-auto` tables, stacked estimate detail, `left-0 md:left-56` sticky bar

### 6.4.3: Light/Dark Theme System ✅ COMPLETE

- `ThemeProvider.tsx` — React context managing `dark`/`light` class on `<html>`, persisted to `localStorage`
- `useTheme()` hook consumed by all client components
- `globals.css` — `html.light { ... }` block overrides all shadcn CSS variables for light mode
- Theme toggle pill in sidebar bottom-left (with account row, version label, settings gear)
- All pages and components fully theme-aware: Dashboard, Estimates, Projects, StatCard, CostTrendChart, EstimateCard, BoardColumn, FilterSelect, Sidebar

### 6.4.4: Custom Dropdown Components ✅ COMPLETE

- `FilterSelect.tsx` — theme-aware custom dropdown replacing all native `<select>` elements
- CA brand styling: translucent panel, checkmark on selected, animated caret chevron
- Closes on outside click via `useRef` + `mousedown` listener

### 6.5: Quote Generation ⚠️ PARTIAL

- Backend: `POST /api/estimates/{id}/quote` returns reportlab-generated PDF with `CA-YYYY-NNNN` sequential numbering
- `quotes` table migrated to Neon dev branch
- ❌ Frontend flow not yet implemented (button wiring, template selector, download trigger)
- ❌ Full T-004A/B/E template content not yet populated (line items, terms, CA letterhead)

### 6.6: User Authentication and Roles ⚠️ PARTIAL

- `ApiKeyMiddleware` in place as dev scaffold (passes all when `ACOUSTIMATOR_API_KEY` env var not set)
- ❌ Real auth (login, roles, session) not implemented — deferred until multi-user need arises

**Phase 6 Deliverable:** Working web app for Commercial Acoustics staff.

---

## Phase 7: Continuous Learning (Ongoing)

### 7.1: Actual vs. Estimated Cost Feedback ❌ NOT STARTED

- Track estimate accuracy after project completion
- Dashboard showing MAPE and bias trends

### 7.2: Model Retraining Pipeline ❌ NOT STARTED

- Scheduled retraining (monthly or after N new projects)
- A/B comparison of new vs. current model
- Automated rollback on regression

### 7.3: Vendor Price Tracking ❌ NOT STARTED

- Alert when material costs change significantly
- Auto-update cost/SF baselines

### 7.4: New Product and Scope Type Handling ❌ NOT STARTED

- Detect unknown product names during extraction
- Workflow to add new catalog entries
- Model adaptation for new categories

**Phase 7 Deliverable:** Self-improving estimation system.

---

## Current Status Summary

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 | 🔄 11/13 | Vercel env vars + Neon↔Vercel integration remaining |
| Phase 1.1 | ✅ | 124 projects, 326 scopes, 245 tests |
| Phase 1.2 | ✅ | 608 PDFs, 99.7% quote#, 98.4% grand total |
| Phase 1.3 | ✅ | 192/192 vendor quotes, 35 vendors |
| Phase 1.4 | ✅ | 126/126 validated, 37 projects with issues identified |
| Phase 1.5 | ✅ | 124 projects in Neon dev branch |
| Phase 1.6 | ✅ | 223 additional cost items, all 12 types |
| Phase 2.1 | ✅ | 74 products, 78.5% match rate |
| Phase 2.2 | ✅ | 64 scopes reclassified, AP eliminated, distribution fixed |
| Phase 2.3 | ✅⚠️ | PriceIndex built; quote dates NULL in DB (bug tracked) |
| Phase 2.4 | ✅ | 192 vendor quotes loaded, 35 vendors, VendorCostTracker built |
| Phase 2.5 | ✅ | Quality dashboard live; ACT ready for ML, others borderline |
| Phase 3.1 | ✅ | FeatureEngineer built, 326-row training CSV |
| Phase 3.2+3.3 | ✅ | ACT 13.5% MAPE ✅, AWP 18.4% ✅, FW 21% ✅; Baffles/WW need more data |
| Phase 3.4 | ✅ | Markup model 16% MAPE, predictions within business ranges |
| Phase 3.5 | ✅ | Labor model, man_days ∝ SF^0.49, 66% MAPE (expected variance) |
| Phase 4 | ✅ | 331 drawings extracted, 8,493 scopes, 5.4M SF, 100% success |
| Phase 5 | ✅ | $68,677 Seven Pines estimate, Excel export, 357 tests |
| Phase 5.5 | ✅ | GitHub CI/CD, branch protection, agent review active |
| Phase 6.1 | ✅ | FastAPI backend, all endpoints, middleware, bug fixes |
| Phase 6.2 | ✅ | Next.js frontend, full API wiring, CA brand theme |
| Phase 6.3 | ✅ | Dashboard (stat cards hardcoded, cost chart empty pending quote_date fix) |
| Phase 6.4 | ✅ | Estimate builder, kanban board, PWA, light/dark theme, custom dropdowns |
| Phase 6.5 | ⚠️ | Quote PDF backend done; frontend flow + full template content not implemented |
| Phase 6.6 | ⚠️ | API key middleware scaffold only; real auth deferred |
| Phase 7 | ❌ | Not started |

---

## Immediate Next Steps (Priority Order)

1. **Fix `quote_date` loader bug** — `src/db/loader.py` needs to persist `extraction_result.project.quote_date` to `projects.quote_date`. This is the single change that unblocks the Cost/SF Trends chart with real historical data.
2. **Dashboard aggregate endpoint** — `GET /api/stats/summary` returning live project count, active estimate count, total SF estimated, avg ACT cost/SF. Replaces hardcoded StatCard values.
3. **Phase 6.5: Complete quote generation** — Wire frontend "Generate Quote" button to `POST /api/estimates/{id}/quote`, add template selector (T-004A/B/E), implement download. Populate full CA template content (line items, clauses, letterhead).
4. **Populate `project_type`** — healthcare/education/church flags already engineered in features.py; persist them to `projects.project_type` to unlock the biggest missing signal for markup + cost models.
5. **Phase 7: Continuous Learning** — Feedback loop for actual vs. estimated costs; monthly model retraining pipeline.

---

## Timeline Summary

| Phase | Duration | Key Output |
|-------|----------|-----------|
| Phase 0 | Done (mostly) | Documentation, schema, project setup |
| Phase 1 | Done (mostly) | Excel + PDF extraction pipeline + DB load |
| Phase 2 | Week 2-3 | Clean, normalized, model-ready dataset |
| Phase 3 | Week 3-4 | Working parametric cost models |
| Phase 4 | Week 4-6 | AI plan reading from architectural drawings |
| Phase 5 | Week 6-7 | End-to-end estimation engine |
| Phase 6 | Week 7-9 | Web application for internal use |
| Phase 7 | Ongoing | Continuous learning and improvement |

---

## Risk Factors

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Excel formats more varied than expected | Phase 1 delay | ✅ Mitigated — Claude API handled all 4 format types |
| Anthropic Tier 1 rate limits | Extraction speed | ✅ Mitigated — 15s delay + exponential backoff |
| Insufficient training data per scope type | Phase 3 accuracy | 326 scopes available; Bayesian priors; transfer learning across types |
| Low product match rate (currently 24.4%) | Phase 2/3 quality | Catalog expansion to 50+ products; manual review queue in place |
| Plan reading accuracy too low | Phase 4 unusable | Start with simple plans; manual SF input as fallback |
| Claude API costs exceed budget | Ongoing | Cache extraction results; batch processing |
