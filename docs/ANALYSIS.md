# Acoustimator Data Analysis

Deep analysis of the Commercial Acoustics historical project dataset. This document serves as the canonical reference for understanding the source data, its structure, quality, and implications for the extraction pipeline and cost modeling.

---

## Table of Contents

1. [Data Source Overview](#data-source-overview)
2. [Folder Structure Analysis](#folder-structure-analysis)
3. [Canonical Document Set](#canonical-document-set)
4. [Excel Buildup Analysis](#excel-buildup-analysis)
5. [Quote Document Analysis](#quote-document-analysis)
6. [Vendor Quote Analysis](#vendor-quote-analysis)
7. [Product and Scope Taxonomy](#product-and-scope-taxonomy)
8. [Email (.msg) Analysis](#email-msg-analysis)
9. [Key Observations](#key-observations)

---

## Data Source Overview

| Metric | Value |
|--------|-------|
| Location | Dropbox `+ITBs` folder |
| Total client folders | 126 (125 active + 1 `++Archive` with 379 historical projects) |
| Total projects | ~504 (125 active + 379 archive) |
| Total files | ~5,000+ |
| Total size | ~186 MB |

### File Type Breakdown

| Extension | Count | Purpose |
|-----------|-------|---------|
| .pdf | 2,928 | Quotes, vendor quotes, plans, specs, takeoffs |
| .xlsx | 823 | Buildups (cost calculations), bid forms |
| .doc/.docx | 621 | Quote templates, bid forms, proposals |
| .msg | 304 | Outlook emails — bid invitations, correspondence |
| .pptx | 10 | Panel layout diagrams |
| .jpg | 9 | Photos, reference images |
| .zip | 8 | Compressed plan sets |
| .csv | 7 | Exported data, vendor price lists |
| .png | 3 | Screenshots, detail images |
| .FCStd | 2 | FreeCAD 3D models |
| .dwg | 1 | AutoCAD drawing |

PDFs dominate at ~58% of all files. Excel buildups represent ~16% and are the primary structured data source. The remaining ~26% is correspondence, templates, and supplementary materials.

> **Note:** The original analysis only counted top-level files; recursive counts are much higher due to Archive subfolders within individual projects and the `++Archive` folder containing 379 historical projects.

---

## Folder Structure Analysis

### Naming Conventions

The `+ITBs` folder uses a prefix-based organization system:

| Prefix | Meaning | Count | Example |
|--------|---------|-------|---------|
| `+` | Active / priority project | ~70 | `+TGH Muma Heart Center` |
| `++` | Archive / completed batch | 1 | `++Archive` (contains 379 historical projects) |
| *(none)* | Standard pipeline / recent | ~52 | `Solomon Partners` |

The `+` prefix denotes projects that are active, awarded, or otherwise prioritized. The absence of a prefix typically indicates newer projects that have not yet been categorized or are in the standard bidding pipeline.

### Archive Subfolders

**57 of 125 active folders** (46%) contain an `Archive` subfolder. These hold prior revisions of buildups, superseded vendor quotes, and earlier takeoff versions. Archive subfolders are critical for understanding revision history but should be treated as secondary data — the parent folder's non-archived files represent the final/current state.

### Folder Count Reconciliation

The source contains 126 total top-level folders: 125 active client project folders plus 1 `++Archive` folder containing 379 historical projects. This gives a total of ~504 projects (125 active + 379 archive). The 125 active project folders are the primary extraction target, with the archive providing additional training data.

---

## Canonical Document Set

Each client folder follows a roughly consistent document pattern. Not every folder contains every document type, but the following represents the canonical set:

| Document Type | File Pattern | Prevalence | Description |
|--------------|-------------|-----------|-------------|
| **Buildup (xlsx)** | `Buildup - [Client].xlsx` | 123/125 (98%) | Internal cost calculations — THE core data |
| **Quote PDF** | `Quote XXXXX - [Client].pdf` | ~101/125 (81%) | Customer-facing quote document |
| **Quote DOC** | `Quote XXXXX - [Client].doc` | ~79/125 (63%) | Editable Word version of the quote |
| **Takeoff/Scope PDF** | Various | Most folders | Marked-up architectural drawings with measurements |
| **Vendor Quote(s)** | Various | ~85 files across folders | Supplier pricing from MDC, FBM, GatorGyp, etc. |
| **Bid Invite (.msg)** | `*.msg` | Many folders | Outlook email from GC with bid invitation |
| **Layout (.pptx)** | `Layout - [Area].pptx` | 15/125 (12%) | Panel layout diagrams for wall panels/baffles |
| **Bid Form (.docx)** | `Bid Form.docx` | Rare (~5%) | Structured bid forms from large GCs |
| **Spec PDFs** | `09 51 00.pdf`, `098430.pdf` | Some folders | CSI Division 09 acoustical specifications |

### Coverage Implications

The 98% prevalence of Excel buildups means the extraction pipeline can rely on this as the primary data source for every project. Quote PDFs at 81% provide a secondary validation source. Vendor quotes at ~68% enable cost-basis tracking.

---

## Excel Buildup Analysis

The Excel buildups are **the single most important data source** in the entire dataset. They contain the actual cost calculations that drive every quote. However, they are semi-structured — no consistent header rows, varying cell positions, and three distinct format families.

### Format A: Simple Single-Scope

**Found in:** Baycare, HCA, small single-scope projects
**Structure:** Vertical key-value pairs

```
Row 1:  [Product Name]           e.g., "Dune on Suprafine"
Row 2:  SF                       2,450
Row 3:  Cost/SF                  $2.34
Row 4:  Material Cost            $5,733.00
Row 5:  Markup                   35%
Row 6:  Material Price           $7,739.55
Row 7:  Man-Days                 4
Row 8:  Labor Price              $2,088.00
Row 9:  Sales Tax                $464.37
Row 10: Total                    $10,291.92
```

**Characteristics:**
- Single column of data, labels in column A, values in column B/C
- One scope per workbook (or one scope per sheet)
- Simplest to parse — direct key-value extraction
- ~30% of all buildups follow this pattern

### Format B: Multi-Scope with Tags

**Found in:** TGH Muma, Solomon Partners, Lifetime Fitness, most medium-to-large projects
**Structure:** Tabular with scope tag column

```
| Tag   | Description            | SF    | Cost/SF | Mat Cost | Markup | Mat Price | Man-Days | Labor   | Tax     | Total     |
|-------|------------------------|-------|---------|----------|--------|-----------|----------|---------|---------|-----------|
| ACT-1 | Dune on Suprafine      | 4,200 | $2.34   | $9,828   | 35%    | $13,268   | 6        | $3,132  | $796    | $17,196   |
| AWP-1 | Zintra Embossed 12mm   | 380   | $24.50  | $9,310   | 25%    | $11,638   | 3        | $1,566  | $698    | $13,902   |
| ACB-1 | Zintra Baffles         | 45 LF | $18/LF  | $810     | 30%    | $1,053    | 1        | $522    | $63     | $1,638    |
|       |                        |       |         |          |        |           |          |         |         |           |
|       | GRAND TOTAL            |       |         |          |        |           |          |         |         | $32,736   |
```

**Characteristics:**
- Multiple scopes in a single sheet, each identified by a tag (ACT-1, AWP-1, etc.)
- Summary row(s) at the bottom with grand total
- Some have sub-totals by scope type
- Column positions are more consistent within this format but still vary between projects
- ~55% of all buildups follow this pattern

### Format C: Complex Multi-Building

**Found in:** OrlandoHealth Wesley Chapel, large hospital/campus projects
**Structure:** Multiple sheets, building/floor breakdowns

```
Sheet "Option A - Armstrong Dune":
  Building 1 - Floor 2:  3,200 SF @ $2.34
  Building 1 - Floor 3:  2,800 SF @ $2.34
  Building 2 - Floor 1:  4,100 SF @ $2.34
  Subtotal:              10,100 SF

Sheet "Option B - USG Radar":
  Building 1 - Floor 2:  3,200 SF @ $1.88
  ...

Sheet "Summary":
  Option A Total: $XX,XXX
  Option B Total: $XX,XXX
```

**Characteristics:**
- Multiple sheets per workbook, each representing a product option or building
- Building and floor-level breakdowns within each sheet
- Comparison pricing across alternatives (Option A vs. Option B)
- Most complex to parse — requires sheet-level iteration and hierarchy detection
- ~15% of all buildups follow this pattern

### Universal Data Fields

Regardless of format, every buildup contains these core fields:

| Field | Description | Always Present | Notes |
|-------|-------------|:--------------:|-------|
| **Square Footage (SF)** | Primary quantity measure | Yes | The fundamental input to every estimate |
| **Product/System** | Tile type + grid system | Yes | Free-form text, e.g., "Dune on Suprafine", "Lyra PB WoodLook on Suprafine" |
| **Cost/SF** | Material unit rate | Yes | Derived from vendor quotes |
| **Markup %** | Margin applied to material cost | Yes | Ranges from **15% to 75%**, varies by scope type and project |
| **Man-Days** | Labor estimate | Yes | Converted at ~$522-558/day rate |
| **Sales Tax** | Florida sales tax on materials | Yes | **6%** on material price (markup-inclusive) |
| **Grand Total** | Final price for the scope | Yes | Material Price + Labor Price + Sales Tax |

### Additional Fields (Present in Some Buildups)

| Field | Prevalence | Notes |
|-------|-----------|-------|
| LF Track | ~20% | Linear feet of mounting track (fabric walls, panels) |
| Yards Fabric | ~15% | Fabric yardage for wrapped panels |
| Vendor/Source | ~30% | Which vendor supplied the pricing |
| Page/Drawing Refs | ~25% | Sheet numbers from architectural plans |
| BuildingConnected Link | ~10% | Link to bid management platform |
| Due Date | ~40% | Bid due date |
| GC/Contact Info | ~50% | General contractor name and contact |

### Markup Ranges by Scope Type

Analysis of markup percentages across all buildups reveals scope-type-dependent patterns:

| Scope Type | Typical Markup Range | Median | Notes |
|-----------|---------------------|--------|-------|
| ACT (Ceiling Tile) | 25%-45% | 35% | Standard commodity, competitive |
| AWP (Wall Panels) | 20%-40% | 30% | Higher material cost, lower margin |
| Baffles | 25%-50% | 35% | Specialty, less price pressure |
| FW (Fabric Wall) | 30%-50% | 40% | Labor-intensive, custom |
| SM (Sound Masking) | 40%-75% | 50% | Equipment + install, high margin |
| WW (WoodWorks) | 15%-35% | 25% | High material cost, slim margin |
| RPG (Specialty) | 30%-50% | 40% | Niche products, less competition |

### Labor Rate Analysis

Man-days are converted to labor price at a consistent daily rate:

| Rate Observed | Time Period | Notes |
|--------------|-------------|-------|
| $522/day | 2023-early 2024 | Standard crew rate |
| $540/day | Mid 2024 | Slight increase |
| $558/day | Late 2024-2025 | Current rate |

The rate represents a loaded crew rate (not per-person), including wages, benefits, insurance, tools, and vehicle. Approximately **1 man-day per 600-800 SF of ACT** and **1 man-day per 100-150 SF of wall panels** are typical benchmarks.

---

## Quote Document Analysis

### Template

Customer-facing quotes use two templates: **T-004A** (General) and **T-004B** (Panel Fab & Install), version 2.29.2024. Both are standardized two-page documents:

**Page 1:**
- Commercial Acoustics letterhead
- Quote number (sequential 5-digit, e.g., `02537` through `06629`)
- Date, contact information, project address
- Line items table: QTY | TYPE | DESCRIPTION | COST PER UNIT | TOTAL
- Revision suffix for re-quotes (e.g., `05906-R1`, `05906-R2`)

**Page 2:**
- Detailed breakdown table (material, labor, tax per scope)
- 13-point terms and conditions
- Signature block

### Quote Numbering

- Sequential 5-digit numbering: `02537` through `06629`
- 326 unique quote numbers found across all projects
- Revision suffix for re-quotes: `-R1`, `-R2`, etc.
- This numbering is traceable and can be used as a unique project identifier
- Gap analysis suggests ~4,000+ quotes have been issued in the range, meaning the 504 projects represent a subset (likely won or actively pursued bids)

### Payment Terms

Payment terms vary by client type:

| Client Type | Typical Terms |
|------------|---------------|
| GC Projects (commercial) | MILESTONE BILLING — progress payments per AIA schedule |
| Direct Clients (owner-direct) | 50% DOWN / BALANCE NET 15 |
| Large GC (national) | NET 30 per application |
| Government/Public | Per contract terms |

---

## Vendor Quote Analysis

### Billing Entity

All vendor quotes are billed to: **Residential Acoustics LLC DBA Commercial Acoustics**, 6301 N Florida Ave, Tampa, FL 33604.

### Key Vendors

| Vendor | Products | Frequency | Notes |
|--------|----------|-----------|-------|
| **MDC Interior Solutions** | Zintra acoustic felt panels, baffles, clouds | High | Primary wall panel supplier |
| **FBM / Foundation Building Materials** | Armstrong, USG ceiling tile and grid | High | Primary ACT supplier |
| **GatorGyp** | ACT grid and tile | High | Regional ACT distributor |
| **Snap-Tex** | Fabric mounting track systems | Medium | Sole track supplier |
| **RPG (Diffusor Systems)** | QRD diffusers, Flutterfree, BAD panels | Low | Specialty acoustics |
| **Arktura** | Decorative acoustic ceilings (SoftGrid, Atmosphera) | Low | High-end architectural |
| **J2 / Turf** | PET felt baffles and panels | Medium | Alternative to Zintra |
| **Soelberg** | Custom acoustic panels, Gesto baffles | Low | Premium/custom |
| **Koroseal / Panawall** | Wall coverings, Type II vinyl | Low | Wall finishing |
| **LW Supply** | Ceiling tile and grid (distribution) | Medium | Alternative to FBM |
| **9Wood** | Wood ceiling systems | Low | Specialty wood |
| **Soundply** | Wood veneer acoustic panels | Low | Specialty wood |
| **ASI Architectural** | Acoustic wood ceilings and walls | Low | Specialty wood |
| **Acoufelt** | Acoustic felt panels and tiles | Low | Specialty felt |
| **Kirei** | EchoPanel PET acoustic panels | Low | Specialty felt |

### Vendor Quote Structure

Vendor quotes typically include:
- Itemized product list with SKUs
- Per-unit pricing (per SF, per LF, per piece)
- Quantity pricing tiers
- Freight/shipping charges (significant — often 8-15% of material cost)
- Lead time information
- Tax status (most quote tax-exempt, CA handles sales tax)

---

## Product and Scope Taxonomy

### Scope Type Classification

| Code | Scope Type | Products | Typical $/SF Range | Unit |
|------|-----------|----------|-------------------|------|
| **ACT** | Acoustical Ceiling Tile | Dune, Cortega, Cirrus, Ultima, Lyra, Mars ClimaPlus, Radar, Fine Fissured | ~$1.57 - $9.44 | SF |
| **AWP** | Acoustic Wall Panels | Fabric-wrapped fiberglass, Zintra felt, MDC Embossed | $21 - $34 | SF |
| **AP** | Acoustic Panels (custom) | Ekko Eraser, FR701 fabric, Guilford of Maine | Varies widely | SF |
| **Baffles** | Ceiling Baffles | Zintra, J2 PET Felt, Turf, Acoufelt | Per LF | LF |
| **FW / SF** | Fabric Wall (Snap-Tex) | Maharam, Knoll Drizzle, Carnegie Xorel, Art Print | $3 - $5 material | SF |
| **SM** | Sound Masking | Electronic masking emitters + controllers | Install-only or w/ equipment | SF / Zone |
| **WW** | WoodWorks | Armstrong WoodWorks Vector, Grille, Forte, Soundply, 9Wood | $20 - $45 | SF |
| **RPG** | Specialty Diffusers | QRD, Flutterfree, Low Frequency Resonators | Per unit | Each |

### Common Product Names (ACT)

The most frequently encountered ceiling tile products, in rough order of prevalence:

1. **Armstrong Dune** — Commodity workhorse, #2 x 2, lay-in
2. **Armstrong Cortega** — Budget option, lower NRC
3. **Armstrong Cirrus** — Smooth face, clean look
4. **Armstrong Ultima** — High-end, high NRC, healthcare
5. **Armstrong Lyra PB** — Square-edge / concealed, premium
6. **USG Radar** — USG alternative to Dune
7. **USG Mars ClimaPlus** — Moisture-resistant, healthcare
8. **Armstrong Fine Fissured** — Standard fissured texture

### Grid Systems

Grid is almost always quoted alongside tile:
- **Armstrong Suprafine** — Standard 15/16" exposed tee
- **Armstrong Prelude** — Heavy-duty 15/16" tee
- **USG DX/DXL** — USG grid alternative
- **Armstrong Silhouette** — Concealed / narrow-face

### Tag Naming Convention

Scope tags in buildups follow the pattern: `{TYPE}-{NUMBER}`, where:
- `TYPE` is the scope code (ACT, AWP, ACB, CL, SF, SM, WW)
- `NUMBER` is a sequential counter within the project
- Examples: `ACT-1`, `ACT-2`, `AWP-1`, `ACB-1`, `CL01`, `SF01`

Some projects use non-standard tags:
- `CL` = Cloud (acoustic ceiling cloud/island)
- `SF` = Snap-Tex Fabric (overlaps with FW)
- `ACB` = Acoustic Ceiling Baffle

---

## Email (.msg) Analysis

304 Outlook .msg files across the dataset. Categories:

| Category | Count (approx.) | Value for Extraction |
|---------|-----------------|---------------------|
| **Bid invitations from GCs** | ~40 | Project details, due dates, scope requirements |
| **RFQ correspondence with vendors** | ~25 | Product specifications, quantities requested |
| **Vendor quotes via email** | ~15 | Pricing (redundant with PDF quotes) |
| **Bid recording sheets** | ~10 | Competitive pricing intelligence |
| **Award notices / LOIs** | ~8 | Win/loss status, awarded amounts |
| **General project correspondence** | ~14 | Misc — change orders, clarifications |

### Extraction Priority

Emails are **low priority** for the initial extraction pipeline. The most valuable metadata (project name, GC, due date) is typically captured in the buildup or folder name. Award notices could be useful for tracking win/loss rates but are not critical for cost modeling.

---

## Key Observations

### Strengths for Machine Learning

1. **Universal pricing formula**: Every buildup follows the same fundamental calculation:
   ```
   Material Cost = SF x Cost/SF
   Material Price = Material Cost x (1 + Markup%)
   Labor Price = Man-Days x Daily Rate
   Sales Tax = Material Price x 6%
   Total = Material Price + Labor Price + Sales Tax
   ```
   This formula is **deterministic** — the ML model's job is to predict the *inputs* (Cost/SF, Markup%, Man-Days), not the arithmetic.

2. **Consistent scope taxonomy**: The 8 scope types (ACT, AWP, AP, Baffles, FW, SM, WW, RPG) appear across all projects. Models can be trained per-scope-type for maximum accuracy.

3. **Sequential quote numbering**: Quote numbers provide a reliable chronological ordering of projects, enabling time-series analysis of pricing trends.

4. **High buildup coverage**: 123 of 125 folders (98%) contain a structured Excel buildup. This is exceptional data coverage for a real-world dataset.

5. **Vendor cost basis**: ~85 vendor quotes provide actual supplier pricing, enabling decomposition of the markup chain (vendor cost -> CA material cost -> customer price).

### Challenges

1. **No header rows in Excel files**: Buildups use label-in-cell patterns rather than proper table headers. The parser must use heuristics or AI to identify field positions.

2. **Inconsistent cell positions**: Column A might be the label column in one buildup and column B in another. Row positions for the same field vary between projects.

3. **Free-form product names**: "Dune on Suprafine", "Armstrong Dune #2404 on Suprafine XL", "Dune, 2x2, Suprafine grid" all refer to the same product. Name normalization is essential.

4. **Multiple sheets per workbook**: Complex projects spread data across 3-8 sheets. The parser must iterate sheets and understand which contain scope data vs. summaries vs. notes.

5. **Formula values as None**: Some cells contain Excel formulas that were never evaluated (workbook was never fully opened/calculated). The extraction pipeline must handle these gracefully.

6. **Three distinct formats**: The parser must detect which format (A, B, or C) a buildup uses before applying the appropriate extraction logic — or use Claude API to handle all formats intelligently.

### Dataset Size Estimate

```
504 projects (125 active + 379 archive) x 1-8 scopes per project = 2,000-4,000+ scope-level training rows
```

This is a **substantial** dataset for parametric modeling. The per-scope-type breakdown (estimated across all 504 projects):
- ACT: ~800-1,200 rows (most common scope)
- AWP: ~300-500 rows
- FW: ~200-350 rows
- Baffles: ~150-250 rows
- WW: ~100-200 rows
- SM: ~80-120 rows
- RPG: ~40-80 rows
- AP: ~100-200 rows

For scope types with fewer than 100 rows, transfer learning or Bayesian approaches may be needed to supplement limited data. For ACT with 800+ rows, traditional ML (Random Forest, XGBoost) should perform very well.

### Data Quality Expectations

Based on manual review of a sample of buildups:

| Quality Metric | Expected | Notes |
|---------------|----------|-------|
| Buildups parseable | 90%+ | Some may be too irregular for automated extraction |
| Fields extractable per buildup | 85%+ | Some fields may be missing or ambiguous |
| Product names normalizable | 95%+ | Most map to a known product with fuzzy matching |
| Quote-to-buildup reconciliation | 80%+ | Quote totals should match buildup grand totals |

### Strategic Recommendations

1. **Use Claude API for Excel parsing** — Rather than writing brittle regex/position-based parsers, send cell contents to Claude for intelligent field extraction. This handles all three formats with a single approach.

2. **Start with ACT scope type** — Highest data volume, simplest pricing (SF x $/SF), most consistent format. Build confidence before tackling complex scope types.

3. **Build a product catalog early** — Normalize all product names to canonical entries in Phase 2. This is prerequisite for meaningful model features.

4. **Track vendor costs separately** — Material cost in the buildup includes markup. Vendor quotes provide the true cost basis. Tracking both enables margin analysis.

5. **Preserve original file references** — Every extracted data point should link back to its source file and cell location for audit and debugging.
