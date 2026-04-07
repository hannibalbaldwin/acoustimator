"""Initial schema - all tables from DATA_SCHEMA.md

Revision ID: 001
Revises:
Create Date: 2026-04-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Enum type definitions
# ---------------------------------------------------------------------------

project_type_enum = postgresql.ENUM(
    "commercial_office",
    "healthcare",
    "education",
    "worship",
    "hospitality",
    "residential",
    "government",
    "entertainment",
    "mixed_use",
    "other",
    name="project_type_enum",
    create_type=False,
)

project_status_enum = postgresql.ENUM(
    "bid",
    "awarded",
    "completed",
    "lost",
    "archived",
    name="project_status_enum",
    create_type=False,
)

scope_type_enum = postgresql.ENUM(
    "ACT",
    "AWP",
    "AP",
    "Baffles",
    "FW",
    "SM",
    "WW",
    "RPG",
    "Other",
    name="scope_type_enum",
    create_type=False,
)

product_category_enum = postgresql.ENUM(
    "ceiling_tile",
    "grid",
    "wall_panel",
    "baffle",
    "fabric",
    "track",
    "diffuser",
    "masking",
    "wood",
    "felt",
    "other",
    name="product_category_enum",
    create_type=False,
)

additional_cost_type_enum = postgresql.ENUM(
    "lift_rental",
    "travel_per_diem",
    "travel_flights",
    "travel_hotels",
    "equipment",
    "consumables",
    "bond",
    "site_visit",
    "punch_list",
    "setup_unload",
    "commission",
    "other",
    name="additional_cost_type_enum",
    create_type=False,
)

estimate_status_enum = postgresql.ENUM(
    "draft",
    "reviewed",
    "finalized",
    "exported",
    name="estimate_status_enum",
    create_type=False,
)

extraction_status_enum = postgresql.ENUM(
    "pending",
    "success",
    "partial",
    "failed",
    name="extraction_status_enum",
    create_type=False,
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create enum types first (must exist before tables reference them)
    # ------------------------------------------------------------------
    project_type_enum.create(op.get_bind(), checkfirst=True)
    project_status_enum.create(op.get_bind(), checkfirst=True)
    scope_type_enum.create(op.get_bind(), checkfirst=True)
    product_category_enum.create(op.get_bind(), checkfirst=True)
    additional_cost_type_enum.create(op.get_bind(), checkfirst=True)
    estimate_status_enum.create(op.get_bind(), checkfirst=True)
    extraction_status_enum.create(op.get_bind(), checkfirst=True)

    # ------------------------------------------------------------------
    # 1. products  (no FK deps)
    # ------------------------------------------------------------------
    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("manufacturer", sa.Text(), nullable=True),
        sa.Column("category", product_category_enum, nullable=True),
        sa.Column("subcategory", sa.Text(), nullable=True),
        sa.Column("typical_cost_per_sf", sa.Numeric(10, 4), nullable=True),
        sa.Column("typical_cost_per_lf", sa.Numeric(10, 4), nullable=True),
        sa.Column("nrc_rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("fire_rating", sa.Text(), nullable=True),
        sa.Column("aliases", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 2. vendors  (no FK deps)
    # ------------------------------------------------------------------
    op.create_table(
        "vendors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("product_categories", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 3. projects  (no FK deps)
    # ------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("folder_name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("gc_name", sa.Text(), nullable=True),
        sa.Column("gc_contact", sa.Text(), nullable=True),
        sa.Column("project_type", project_type_enum, nullable=True),
        sa.Column("quote_number", sa.Text(), nullable=True),
        sa.Column("quote_date", sa.Date(), nullable=True),
        sa.Column("bid_due_date", sa.Date(), nullable=True),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column(
            "status",
            project_status_enum,
            server_default=sa.text("'bid'"),
            nullable=True,
        ),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 4. scopes  (FK: projects, products)
    # ------------------------------------------------------------------
    op.create_table(
        "scopes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.Text(), nullable=True),
        sa.Column("scope_type", scope_type_enum, nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("square_footage", sa.Numeric(12, 2), nullable=True),
        sa.Column("linear_footage", sa.Numeric(12, 2), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit", sa.String(), server_default=sa.text("'SF'"), nullable=True),
        sa.Column("cost_per_unit", sa.Numeric(10, 4), nullable=True),
        sa.Column("material_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("markup_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("material_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("man_days", sa.Numeric(8, 2), nullable=True),
        sa.Column("daily_labor_rate", sa.Numeric(8, 2), nullable=True),
        sa.Column("labor_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("labor_base_rate", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "labor_hours_per_day",
            sa.Numeric(4, 1),
            server_default=sa.text("8"),
            nullable=True,
        ),
        sa.Column("labor_multiplier", sa.Numeric(4, 2), nullable=True),
        sa.Column("scrap_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "sales_tax_pct",
            sa.Numeric(5, 4),
            server_default=sa.text("0.06"),
            nullable=True,
        ),
        sa.Column("county_surtax_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("county_surtax_cap", sa.Numeric(10, 2), nullable=True),
        sa.Column("sales_tax", sa.Numeric(12, 2), nullable=True),
        sa.Column("total", sa.Numeric(12, 2), nullable=True),
        sa.Column("drawing_references", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extraction_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("source_file", sa.Text(), nullable=True),
        sa.Column("source_sheet", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 5. vendor_quotes  (FK: projects, vendors)
    # ------------------------------------------------------------------
    op.create_table(
        "vendor_quotes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quote_number", sa.Text(), nullable=True),
        sa.Column("quote_date", sa.Date(), nullable=True),
        sa.Column("items", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("freight", sa.Numeric(10, 2), nullable=True),
        sa.Column("sales_tax", sa.Numeric(10, 2), nullable=True),
        sa.Column("total", sa.Numeric(12, 2), nullable=True),
        sa.Column("lead_time", sa.Text(), nullable=True),
        sa.Column("source_file", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 6. additional_costs  (FK: projects)
    # ------------------------------------------------------------------
    op.create_table(
        "additional_costs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cost_type", additional_cost_type_enum, nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_file", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 7. estimates  (no FK deps)
    # ------------------------------------------------------------------
    op.create_table(
        "estimates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("project_address", sa.Text(), nullable=True),
        sa.Column("gc_name", sa.Text(), nullable=True),
        sa.Column("project_type", project_type_enum, nullable=True),
        sa.Column("source_plans", sa.ARRAY(sa.Text()), nullable=True),
        sa.Column(
            "status",
            estimate_status_enum,
            server_default=sa.text("'draft'"),
            nullable=True,
        ),
        sa.Column("total_estimate", sa.Numeric(12, 2), nullable=True),
        sa.Column("overall_confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 8. estimate_scopes  (FK: estimates, products)
    # ------------------------------------------------------------------
    op.create_table(
        "estimate_scopes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("estimate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.Text(), nullable=True),
        sa.Column("scope_type", scope_type_enum, nullable=True),
        sa.Column("product_name", sa.Text(), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("square_footage", sa.Numeric(12, 2), nullable=True),
        sa.Column("linear_footage", sa.Numeric(12, 2), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit", sa.String(), server_default=sa.text("'SF'"), nullable=True),
        sa.Column("cost_per_unit", sa.Numeric(10, 4), nullable=True),
        sa.Column("material_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("markup_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("material_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("man_days", sa.Numeric(8, 2), nullable=True),
        sa.Column("daily_labor_rate", sa.Numeric(8, 2), nullable=True),
        sa.Column("labor_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("labor_base_rate", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "labor_hours_per_day",
            sa.Numeric(4, 1),
            server_default=sa.text("8"),
            nullable=True,
        ),
        sa.Column("labor_multiplier", sa.Numeric(4, 2), nullable=True),
        sa.Column("scrap_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "sales_tax_pct",
            sa.Numeric(5, 4),
            server_default=sa.text("0.06"),
            nullable=True,
        ),
        sa.Column(
            "county_surtax_rate",
            sa.Numeric(5, 4),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column(
            "county_surtax_cap",
            sa.Numeric(10, 2),
            server_default=sa.text("5000"),
            nullable=True,
        ),
        sa.Column("sales_tax", sa.Numeric(12, 2), nullable=True),
        sa.Column("total", sa.Numeric(12, 2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "comparable_project_ids",
            sa.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column("ai_notes", sa.Text(), nullable=True),
        sa.Column("room_name", sa.Text(), nullable=True),
        sa.Column("floor", sa.Text(), nullable=True),
        sa.Column("building", sa.Text(), nullable=True),
        sa.Column("drawing_reference", sa.Text(), nullable=True),
        sa.Column(
            "manually_adjusted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # 9. extraction_runs  (FK: projects)
    # ------------------------------------------------------------------
    op.create_table(
        "extraction_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_file", sa.Text(), nullable=False),
        sa.Column("file_type", sa.Text(), nullable=False),
        sa.Column("extraction_status", extraction_status_enum, nullable=False),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    # projects
    op.create_index("idx_projects_quote_number", "projects", ["quote_number"])
    op.create_index("idx_projects_quote_date", "projects", ["quote_date"])
    op.create_index("idx_projects_project_type", "projects", ["project_type"])
    op.create_index("idx_projects_status", "projects", ["status"])
    op.create_index("idx_projects_gc_name", "projects", ["gc_name"])

    # scopes
    op.create_index("idx_scopes_project_id", "scopes", ["project_id"])
    op.create_index("idx_scopes_scope_type", "scopes", ["scope_type"])
    op.create_index("idx_scopes_product_name", "scopes", ["product_name"])
    op.create_index("idx_scopes_product_id", "scopes", ["product_id"])

    # products
    op.create_index("idx_products_canonical_name", "products", ["canonical_name"])
    op.create_index("idx_products_manufacturer", "products", ["manufacturer"])
    op.create_index("idx_products_category", "products", ["category"])
    op.create_index(
        "idx_products_canonical_name_mfr",
        "products",
        ["canonical_name", "manufacturer"],
        unique=True,
    )

    # vendor_quotes
    op.create_index("idx_vendor_quotes_project_id", "vendor_quotes", ["project_id"])
    op.create_index("idx_vendor_quotes_vendor_id", "vendor_quotes", ["vendor_id"])
    op.create_index("idx_vendor_quotes_quote_date", "vendor_quotes", ["quote_date"])

    # additional_costs
    op.create_index("idx_additional_costs_project_id", "additional_costs", ["project_id"])
    op.create_index("idx_additional_costs_cost_type", "additional_costs", ["cost_type"])

    # estimates
    op.create_index("idx_estimates_status", "estimates", ["status"])
    op.create_index("idx_estimates_created_at", "estimates", ["created_at"])

    # estimate_scopes
    op.create_index("idx_estimate_scopes_estimate_id", "estimate_scopes", ["estimate_id"])
    op.create_index("idx_estimate_scopes_scope_type", "estimate_scopes", ["scope_type"])

    # extraction_runs
    op.create_index("idx_extraction_runs_project", "extraction_runs", ["project_id"])
    op.create_index("idx_extraction_runs_status", "extraction_runs", ["extraction_status"])


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Drop indexes
    # ------------------------------------------------------------------
    op.drop_index("idx_extraction_runs_status", table_name="extraction_runs")
    op.drop_index("idx_extraction_runs_project", table_name="extraction_runs")
    op.drop_index("idx_estimate_scopes_scope_type", table_name="estimate_scopes")
    op.drop_index("idx_estimate_scopes_estimate_id", table_name="estimate_scopes")
    op.drop_index("idx_estimates_created_at", table_name="estimates")
    op.drop_index("idx_estimates_status", table_name="estimates")
    op.drop_index("idx_additional_costs_cost_type", table_name="additional_costs")
    op.drop_index("idx_additional_costs_project_id", table_name="additional_costs")
    op.drop_index("idx_vendor_quotes_quote_date", table_name="vendor_quotes")
    op.drop_index("idx_vendor_quotes_vendor_id", table_name="vendor_quotes")
    op.drop_index("idx_vendor_quotes_project_id", table_name="vendor_quotes")
    op.drop_index("idx_products_canonical_name_mfr", table_name="products")
    op.drop_index("idx_products_category", table_name="products")
    op.drop_index("idx_products_manufacturer", table_name="products")
    op.drop_index("idx_products_canonical_name", table_name="products")
    op.drop_index("idx_scopes_product_id", table_name="scopes")
    op.drop_index("idx_scopes_product_name", table_name="scopes")
    op.drop_index("idx_scopes_scope_type", table_name="scopes")
    op.drop_index("idx_scopes_project_id", table_name="scopes")
    op.drop_index("idx_projects_gc_name", table_name="projects")
    op.drop_index("idx_projects_status", table_name="projects")
    op.drop_index("idx_projects_project_type", table_name="projects")
    op.drop_index("idx_projects_quote_date", table_name="projects")
    op.drop_index("idx_projects_quote_number", table_name="projects")

    # ------------------------------------------------------------------
    # Drop tables (reverse dependency order)
    # ------------------------------------------------------------------
    op.drop_table("extraction_runs")
    op.drop_table("estimate_scopes")
    op.drop_table("estimates")
    op.drop_table("additional_costs")
    op.drop_table("vendor_quotes")
    op.drop_table("scopes")
    op.drop_table("projects")
    op.drop_table("vendors")
    op.drop_table("products")

    # ------------------------------------------------------------------
    # Drop enum types after tables are gone
    # ------------------------------------------------------------------
    extraction_status_enum.drop(op.get_bind(), checkfirst=True)
    estimate_status_enum.drop(op.get_bind(), checkfirst=True)
    additional_cost_type_enum.drop(op.get_bind(), checkfirst=True)
    product_category_enum.drop(op.get_bind(), checkfirst=True)
    scope_type_enum.drop(op.get_bind(), checkfirst=True)
    project_status_enum.drop(op.get_bind(), checkfirst=True)
    project_type_enum.drop(op.get_bind(), checkfirst=True)
