# Acoustimator Database Schema

Complete database schema documentation. This is the single source of truth for all table definitions, relationships, indexes, and constraints.

---

## Entity Relationship Overview

```
projects ──< scopes >── products
    │
    ├──< vendor_quotes >── vendors
    │
    ├──< additional_costs
    │
estimates ──< estimate_scopes >── products
```

- A **project** has many **scopes** (one per line item: ACT-1, AWP-1, etc.)
- A **scope** optionally links to a normalized **product**
- A **project** has many **vendor_quotes** from different **vendors**
- An **estimate** (AI-generated) has many **estimate_scopes**
- An **estimate_scope** references comparable **projects** used in prediction

---

## Core Tables

### projects

The central entity. Each row represents one historical client project, corresponding to one folder in the Dropbox +ITBs directory.

```sql
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    folder_name     TEXT,
    address         TEXT,
    gc_name         TEXT,
    gc_contact      TEXT,
    project_type    TEXT CHECK (project_type IN (
                        'commercial_office', 'healthcare', 'education',
                        'worship', 'hospitality', 'residential',
                        'government', 'entertainment', 'mixed_use', 'other'
                    )),
    quote_number    TEXT,
    quote_date      DATE,
    payment_terms   TEXT,
    status          TEXT CHECK (status IN (
                        'bid', 'awarded', 'completed', 'lost', 'archived'
                    )) DEFAULT 'bid',
    source_path     TEXT,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key, auto-generated |
| name | TEXT | No | Project name (e.g., "TGH Muma Heart Center") |
| folder_name | TEXT | Yes | Original folder name from Dropbox (e.g., "+TGH Muma Heart Center") |
| address | TEXT | Yes | Project site address |
| gc_name | TEXT | Yes | General contractor name |
| gc_contact | TEXT | Yes | GC contact person / email / phone |
| project_type | TEXT | Yes | Project category — constrained to enum values |
| quote_number | TEXT | Yes | Commercial Acoustics quote number (e.g., "05906") |
| quote_date | DATE | Yes | Date the quote was issued |
| payment_terms | TEXT | Yes | Payment terms (e.g., "MILESTONE BILLING", "50% DOWN/NET 15") |
| status | TEXT | Yes | Project status — defaults to "bid" |
| source_path | TEXT | Yes | Absolute path to original folder on disk |
| notes | TEXT | Yes | Free-form notes from extraction or manual entry |
| created_at | TIMESTAMP | No | Record creation timestamp |
| updated_at | TIMESTAMP | No | Last modification timestamp |

**Notes:**
- `quote_number` is not unique — revisions share the base number (05906, 05906-R1, 05906-R2)
- `project_type` is inferred from project name, GC, and scope types during extraction
- `source_path` enables tracing any data point back to its original file

---

### scopes

Individual scope line items within a project. Each scope represents one product/service type being quoted (e.g., ACT-1 for ceiling tile in area 1, AWP-1 for wall panels).

```sql
CREATE TABLE scopes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tag                 TEXT,
    scope_type          TEXT CHECK (scope_type IN (
                            'ACT', 'AWP', 'AP', 'Baffles', 'FW', 'SM', 'WW', 'RPG', 'Other'
                        )),
    product_name        TEXT,
    product_id          UUID REFERENCES products(id),
    square_footage      DECIMAL(12,2),
    linear_footage      DECIMAL(12,2),
    quantity            DECIMAL(12,2),
    unit                TEXT DEFAULT 'SF',
    cost_per_unit       DECIMAL(10,4),
    material_cost       DECIMAL(12,2),
    markup_pct          DECIMAL(5,4),
    material_price      DECIMAL(12,2),
    man_days            DECIMAL(8,2),
    daily_labor_rate    DECIMAL(8,2),
    labor_price         DECIMAL(12,2),
    labor_base_rate     DECIMAL(6,2),
    labor_hours_per_day DECIMAL(4,1) DEFAULT 8,
    labor_multiplier    DECIMAL(4,2),
    scrap_rate          DECIMAL(5,4),
    sales_tax_pct       DECIMAL(5,4) DEFAULT 0.06,
    county_surtax_rate  DECIMAL(5,4),
    county_surtax_cap   DECIMAL(10,2),
    sales_tax           DECIMAL(12,2),
    total               DECIMAL(12,2),
    drawing_references  TEXT[],
    notes               TEXT,
    extraction_confidence DECIMAL(3,2),
    source_file         TEXT,
    source_sheet        TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key |
| project_id | UUID | No | FK to projects — cascading delete |
| tag | TEXT | Yes | Scope tag from buildup (e.g., "ACT-1", "AWP-1", "CL01") |
| scope_type | TEXT | Yes | Canonical scope type classification |
| product_name | TEXT | Yes | Free-form product name as written in the buildup |
| product_id | UUID | Yes | FK to normalized product catalog (populated in Phase 2) |
| square_footage | DECIMAL | Yes | Primary quantity — SF for most scope types |
| linear_footage | DECIMAL | Yes | LF for baffles, track, trim |
| quantity | DECIMAL | Yes | Generic quantity for per-unit items (RPG diffusers, etc.) |
| unit | TEXT | Yes | Unit of measure — SF, LF, EA, SY (square yards) |
| cost_per_unit | DECIMAL | Yes | Material cost per unit (cost/SF, cost/LF, etc.) |
| material_cost | DECIMAL | Yes | quantity x cost_per_unit |
| markup_pct | DECIMAL | Yes | Markup as a decimal (0.35 = 35%) |
| material_price | DECIMAL | Yes | material_cost x (1 + markup_pct) |
| man_days | DECIMAL | Yes | Labor estimate in man-days |
| daily_labor_rate | DECIMAL | Yes | $/day rate used (e.g., 522.00, 558.00) |
| labor_price | DECIMAL | Yes | man_days x daily_labor_rate |
| labor_base_rate | DECIMAL | Yes | Hourly base rate (e.g., 45.00, 46.00, 50.00) |
| labor_hours_per_day | DECIMAL | Yes | Hours per day — defaults to 8, some projects use 10 |
| labor_multiplier | DECIMAL | Yes | Burden/overhead multiplier (e.g., 1.35 to 1.80) |
| scrap_rate | DECIMAL | Yes | Waste factor as decimal (e.g., 0.10 = 10% scrap) |
| sales_tax_pct | DECIMAL | Yes | Tax rate — defaults to 6% (Florida) |
| county_surtax_rate | DECIMAL | Yes | FL county discretionary surtax rate (e.g., 0.015 = 1.5%) |
| county_surtax_cap | DECIMAL | Yes | Surtax cap per transaction (e.g., 5000.00 for FL) |
| sales_tax | DECIMAL | Yes | material_price x sales_tax_pct + min(surtax_rate x material_price, surtax_cap) |
| total | DECIMAL | Yes | material_price + labor_price + sales_tax |
| drawing_references | TEXT[] | Yes | Sheet numbers from architectural plans |
| notes | TEXT | Yes | Extraction notes, anomalies |
| extraction_confidence | DECIMAL | Yes | 0.00-1.00 confidence from Claude extraction |
| source_file | TEXT | Yes | Original Excel file path |
| source_sheet | TEXT | Yes | Sheet name within the workbook |
| created_at | TIMESTAMP | No | Record creation timestamp |

**Notes:**
- `markup_pct` is stored as a decimal (0.35), not a percentage (35%). This avoids confusion in calculations.
- `square_footage` vs. `linear_footage` vs. `quantity` — most scopes use SF, but baffles use LF and specialty items use EA. The `unit` column disambiguates.
- `product_id` is nullable because it is populated during Phase 2 (normalization), not during initial extraction.
- `extraction_confidence` is set by the Claude API extraction pipeline to indicate how confident the parser was in the extracted values.

---

### products

Normalized product catalog. Maps the many free-form product name variations found in buildups to canonical product entries.

```sql
CREATE TABLE products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name  TEXT NOT NULL,
    manufacturer    TEXT,
    category        TEXT CHECK (category IN (
                        'ceiling_tile', 'grid', 'wall_panel', 'baffle',
                        'fabric', 'track', 'diffuser', 'masking',
                        'wood', 'felt', 'other'
                    )),
    subcategory     TEXT,
    typical_cost_per_sf DECIMAL(10,4),
    typical_cost_per_lf DECIMAL(10,4),
    nrc_rating      DECIMAL(3,2),
    fire_rating     TEXT,
    aliases         TEXT[],
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key |
| canonical_name | TEXT | No | Standardized product name (e.g., "Armstrong Dune") |
| manufacturer | TEXT | Yes | Manufacturer name (e.g., "Armstrong", "USG", "MDC") |
| category | TEXT | Yes | Product category — constrained to enum values |
| subcategory | TEXT | Yes | Finer classification (e.g., "lay-in" vs. "tegular" for ceiling tile) |
| typical_cost_per_sf | DECIMAL | Yes | Average cost/SF across all historical scopes using this product |
| typical_cost_per_lf | DECIMAL | Yes | Average cost/LF for linear products (baffles, track) |
| nrc_rating | DECIMAL | Yes | Noise Reduction Coefficient (0.00-1.00) |
| fire_rating | TEXT | Yes | Fire rating classification (Class A, Class 1, etc.) |
| aliases | TEXT[] | Yes | All name variations seen in buildups |
| notes | TEXT | Yes | Product notes, specifications |
| created_at | TIMESTAMP | No | Record creation timestamp |
| updated_at | TIMESTAMP | No | Last modification timestamp |

**Example entries:**

| canonical_name | manufacturer | category | aliases |
|---------------|-------------|----------|---------|
| Armstrong Dune | Armstrong | ceiling_tile | {"Dune", "Dune on Suprafine", "Armstrong Dune #2404", "Dune 2x2"} |
| Armstrong Suprafine | Armstrong | grid | {"Suprafine", "Suprafine XL", "Armstrong Suprafine 15/16"} |
| Zintra Embossed 12mm | MDC | wall_panel | {"Zintra", "MDC Zintra Embossed", "Zintra 12mm Felt"} |

---

### vendors

Vendor/supplier master list.

```sql
CREATE TABLE vendors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    full_name           TEXT,
    contact_name        TEXT,
    email               TEXT,
    phone               TEXT,
    address             TEXT,
    product_categories  TEXT[],
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key |
| name | TEXT | No | Short vendor name (e.g., "FBM", "MDC", "GatorGyp") |
| full_name | TEXT | Yes | Full legal name (e.g., "Foundation Building Materials") |
| contact_name | TEXT | Yes | Primary contact person |
| email | TEXT | Yes | Contact email |
| phone | TEXT | Yes | Contact phone |
| address | TEXT | Yes | Vendor address |
| product_categories | TEXT[] | Yes | Categories supplied (e.g., {"ceiling_tile", "grid"}) |
| notes | TEXT | Yes | Vendor notes |
| created_at | TIMESTAMP | No | Record creation timestamp |

---

### vendor_quotes

Individual vendor quotes received for projects.

```sql
CREATE TABLE vendor_quotes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    vendor_id       UUID REFERENCES vendors(id),
    quote_number    TEXT,
    quote_date      DATE,
    items           JSONB,
    freight         DECIMAL(10,2),
    sales_tax       DECIMAL(10,2),
    total           DECIMAL(12,2),
    lead_time       TEXT,
    source_file     TEXT,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key |
| project_id | UUID | No | FK to projects |
| vendor_id | UUID | Yes | FK to vendors (populated during normalization) |
| quote_number | TEXT | Yes | Vendor's quote/order number |
| quote_date | DATE | Yes | Date of vendor quote |
| items | JSONB | Yes | Array of line items (see structure below) |
| freight | DECIMAL | Yes | Shipping/freight charges |
| sales_tax | DECIMAL | Yes | Tax on vendor quote (usually $0 — tax-exempt) |
| total | DECIMAL | Yes | Quote total including freight |
| lead_time | TEXT | Yes | Stated lead time (e.g., "2-3 weeks") |
| source_file | TEXT | Yes | Path to original vendor quote file |
| notes | TEXT | Yes | Extraction notes |
| created_at | TIMESTAMP | No | Record creation timestamp |

**Items JSONB structure:**

```json
[
    {
        "product": "Armstrong Dune #2404 2x2",
        "sku": "2404",
        "quantity": 150,
        "unit": "CTN",
        "unit_cost": 42.50,
        "total": 6375.00
    },
    {
        "product": "Suprafine XL 15/16\" Main Tee",
        "sku": "XL7341",
        "quantity": 85,
        "unit": "EA",
        "unit_cost": 12.75,
        "total": 1083.75
    }
]
```

---

### additional_costs

Non-standard cost items that appear in buildups beyond the core material/labor/tax formula.

```sql
CREATE TABLE additional_costs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    cost_type       TEXT CHECK (cost_type IN (
                        'lift_rental', 'travel_per_diem', 'travel_flights',
                        'travel_hotels', 'equipment', 'consumables',
                        'bond', 'site_visit', 'punch_list', 'setup_unload',
                        'commission', 'other'
                    )),
    description     TEXT,
    amount          DECIMAL(12,2),
    notes           TEXT,
    source_file     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key |
| project_id | UUID | No | FK to projects — cascading delete |
| cost_type | TEXT | Yes | Categorized cost type — constrained to enum values |
| description | TEXT | Yes | Free-form description (e.g., "Scissor lift 2 weeks", "Per diem 6 days") |
| amount | DECIMAL | Yes | Dollar amount for this cost item |
| notes | TEXT | Yes | Extraction notes |
| source_file | TEXT | Yes | Original file path |
| created_at | TIMESTAMP | No | Record creation timestamp |

**Typical values by cost_type:**
- `lift_rental`: $500-$1,800
- `travel_per_diem`: $65-75/day x man-days
- `travel_flights`: $400-550/trip
- `travel_hotels`: $150/night
- `equipment`: Varies (scissor boom, compressor, table saw, scaffolding)
- `consumables`: 2-10% of material price
- `bond`: 3% of total (Payment & Performance bond)
- `site_visit`: $750 or 1 man-day equivalent
- `punch_list`: 0.85-2 man-days equivalent
- `setup_unload`: 10% of install days equivalent
- `commission`: Flat fee (sound masking tune/balance)

---

### estimates

AI-generated estimates for new projects. Created when a user uploads plans or manually creates an estimate.

```sql
CREATE TABLE estimates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    project_address TEXT,
    gc_name         TEXT,
    project_type    TEXT CHECK (project_type IN (
                        'commercial_office', 'healthcare', 'education',
                        'worship', 'hospitality', 'residential',
                        'government', 'entertainment', 'mixed_use', 'other'
                    )),
    source_plans    TEXT[],
    status          TEXT CHECK (status IN (
                        'draft', 'reviewed', 'finalized', 'exported'
                    )) DEFAULT 'draft',
    total_estimate  DECIMAL(12,2),
    overall_confidence DECIMAL(3,2),
    created_by      TEXT,
    reviewed_by     TEXT,
    reviewed_at     TIMESTAMP,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key |
| name | TEXT | No | Estimate name (e.g., "AdventHealth New Smyrna - Bid") |
| project_address | TEXT | Yes | Project site address |
| gc_name | TEXT | Yes | General contractor |
| project_type | TEXT | Yes | Project category |
| source_plans | TEXT[] | Yes | Paths to uploaded plan PDF files |
| status | TEXT | Yes | Workflow status — draft -> reviewed -> finalized -> exported |
| total_estimate | DECIMAL | Yes | Sum of all estimate_scopes totals |
| overall_confidence | DECIMAL | Yes | Weighted average of scope confidence scores |
| created_by | TEXT | Yes | User who created the estimate |
| reviewed_by | TEXT | Yes | User who reviewed/approved |
| reviewed_at | TIMESTAMP | Yes | When the estimate was reviewed |
| notes | TEXT | Yes | Estimator notes |
| created_at | TIMESTAMP | No | Record creation timestamp |
| updated_at | TIMESTAMP | No | Last modification timestamp |

---

### estimate_scopes

Individual scope line items within an AI-generated estimate. Mirrors the `scopes` table structure with additional AI-specific fields.

```sql
CREATE TABLE estimate_scopes (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    estimate_id             UUID NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    tag                     TEXT,
    scope_type              TEXT CHECK (scope_type IN (
                                'ACT', 'AWP', 'AP', 'Baffles', 'FW', 'SM', 'WW', 'RPG', 'Other'
                            )),
    product_name            TEXT,
    product_id              UUID REFERENCES products(id),
    square_footage          DECIMAL(12,2),
    linear_footage          DECIMAL(12,2),
    quantity                DECIMAL(12,2),
    unit                    TEXT DEFAULT 'SF',
    cost_per_unit           DECIMAL(10,4),
    material_cost           DECIMAL(12,2),
    markup_pct              DECIMAL(5,4),
    material_price          DECIMAL(12,2),
    man_days                DECIMAL(8,2),
    daily_labor_rate        DECIMAL(8,2),
    labor_price             DECIMAL(12,2),
    sales_tax_pct           DECIMAL(5,4) DEFAULT 0.06,
    sales_tax               DECIMAL(12,2),
    total                   DECIMAL(12,2),
    confidence_score        DECIMAL(3,2),
    comparable_project_ids  UUID[],
    ai_notes                TEXT,
    room_name               TEXT,
    floor                   TEXT,
    building                TEXT,
    drawing_reference       TEXT,
    manually_adjusted       BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| *(same cost fields as scopes)* | | | See scopes table above |
| confidence_score | DECIMAL | Yes | 0.00-1.00 — how confident the model is in this estimate |
| comparable_project_ids | UUID[] | Yes | IDs of historical projects used as basis for this estimate |
| ai_notes | TEXT | Yes | AI explanation of estimate rationale |
| room_name | TEXT | Yes | Room name from plan reading (e.g., "Lobby", "Conference Room 201") |
| floor | TEXT | Yes | Floor from plan reading |
| building | TEXT | Yes | Building name from plan reading |
| drawing_reference | TEXT | Yes | Plan sheet number where this scope was identified |
| manually_adjusted | BOOLEAN | No | Whether the user has overridden the AI estimate |
| created_at | TIMESTAMP | No | Record creation timestamp |
| updated_at | TIMESTAMP | No | Last modification timestamp |

---

## Indexes

```sql
-- Projects
CREATE INDEX idx_projects_quote_number ON projects(quote_number);
CREATE INDEX idx_projects_quote_date ON projects(quote_date);
CREATE INDEX idx_projects_project_type ON projects(project_type);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_gc_name ON projects(gc_name);

-- Scopes
CREATE INDEX idx_scopes_project_id ON scopes(project_id);
CREATE INDEX idx_scopes_scope_type ON scopes(scope_type);
CREATE INDEX idx_scopes_product_name ON scopes(product_name);
CREATE INDEX idx_scopes_product_id ON scopes(product_id);

-- Products
CREATE INDEX idx_products_canonical_name ON products(canonical_name);
CREATE INDEX idx_products_manufacturer ON products(manufacturer);
CREATE INDEX idx_products_category ON products(category);
CREATE UNIQUE INDEX idx_products_canonical_name_mfr ON products(canonical_name, manufacturer);

-- Vendor Quotes
CREATE INDEX idx_vendor_quotes_project_id ON vendor_quotes(project_id);
CREATE INDEX idx_vendor_quotes_vendor_id ON vendor_quotes(vendor_id);
CREATE INDEX idx_vendor_quotes_quote_date ON vendor_quotes(quote_date);

-- Additional Costs
CREATE INDEX idx_additional_costs_project_id ON additional_costs(project_id);
CREATE INDEX idx_additional_costs_cost_type ON additional_costs(cost_type);

-- Estimates
CREATE INDEX idx_estimates_status ON estimates(status);
CREATE INDEX idx_estimates_created_at ON estimates(created_at);

-- Estimate Scopes
CREATE INDEX idx_estimate_scopes_estimate_id ON estimate_scopes(estimate_id);
CREATE INDEX idx_estimate_scopes_scope_type ON estimate_scopes(scope_type);
```

---

## Enum Reference

### project_type
| Value | Description |
|-------|-------------|
| commercial_office | Office, retail, restaurant, mixed commercial |
| healthcare | Hospital, clinic, medical office, senior living |
| education | School, university, library |
| worship | Church, synagogue, mosque |
| hospitality | Hotel, resort, event venue |
| residential | Multi-family, condo, luxury residential |
| government | Government building, courthouse, military |
| entertainment | Theater, arena, performing arts, recreation |
| mixed_use | Multiple categories in one project |
| other | Uncategorized |

### scope_type
| Value | Description | Common Products |
|-------|-------------|-----------------|
| ACT | Acoustical Ceiling Tile | Dune, Cortega, Cirrus, Ultima, Lyra, Radar |
| AWP | Acoustic Wall Panels | Zintra, fabric-wrapped fiberglass, MDC |
| AP | Acoustic Panels (custom) | Ekko Eraser, FR701 fabric panels |
| Baffles | Ceiling Baffles | Zintra, J2, Turf, Acoufelt PET felt |
| FW | Fabric Wall (Snap-Tex) | Maharam, Knoll, Carnegie Xorel |
| SM | Sound Masking | Electronic masking systems |
| WW | WoodWorks | Armstrong WoodWorks, Soundply, 9Wood |
| RPG | Specialty Diffusers | QRD, Flutterfree |
| Other | Uncategorized | Catch-all for new/rare scope types |

### project status
| Value | Description |
|-------|-------------|
| bid | Quote submitted, awaiting decision |
| awarded | Project won, in progress or scheduled |
| completed | Project finished |
| lost | Bid not selected |
| archived | Old/inactive project |

### estimate status
| Value | Description |
|-------|-------------|
| draft | AI-generated, not yet reviewed |
| reviewed | Reviewed by estimator, may have manual adjustments |
| finalized | Approved, ready for quote generation |
| exported | Quote/buildup has been generated and exported |

---

## SQLite Compatibility Notes

For Phase 1-3 development using SQLite:

- `UUID` columns use `TEXT` type with Python-generated UUIDs
- `JSONB` columns use `TEXT` type with JSON serialized strings
- `TEXT[]` array columns use `TEXT` type with JSON serialized arrays
- `gen_random_uuid()` is replaced by application-level UUID generation
- `DECIMAL` uses `REAL` type (SQLite does not have true decimal)
- `CHECK` constraints are supported in SQLite 3.25+
- `TIMESTAMP` uses `TEXT` with ISO 8601 format strings

The SQLAlchemy ORM layer abstracts these differences — the same model code works with both SQLite and PostgreSQL.

---

## Migration Strategy

**Phase 1-3 (SQLite):**
- Schema created directly from SQLAlchemy models via `Base.metadata.create_all()`
- No formal migrations needed — database can be recreated from extraction pipeline

**Phase 4+ (PostgreSQL):**
- Migrate to PostgreSQL using Alembic
- Initial migration creates all tables from the current SQLAlchemy models
- Subsequent migrations handle schema evolution
- Data migrated from SQLite using `seed_db.py` script
