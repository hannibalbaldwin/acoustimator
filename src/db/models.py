"""SQLAlchemy ORM models for the Acoustimator database schema."""

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- Enum types ---


class ProjectType(enum.StrEnum):
    COMMERCIAL_OFFICE = "commercial_office"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    WORSHIP = "worship"
    HOSPITALITY = "hospitality"
    RESIDENTIAL = "residential"
    GOVERNMENT = "government"
    ENTERTAINMENT = "entertainment"
    MIXED_USE = "mixed_use"
    OTHER = "other"


class ProjectStatus(enum.StrEnum):
    BID = "bid"
    AWARDED = "awarded"
    COMPLETED = "completed"
    LOST = "lost"
    ARCHIVED = "archived"


class ScopeType(enum.StrEnum):
    ACT = "ACT"
    AWP = "AWP"
    AP = "AP"
    BAFFLES = "Baffles"
    FW = "FW"
    SM = "SM"
    WW = "WW"
    RPG = "RPG"
    OTHER = "Other"


class ProductCategory(enum.StrEnum):
    CEILING_TILE = "ceiling_tile"
    GRID = "grid"
    WALL_PANEL = "wall_panel"
    BAFFLE = "baffle"
    FABRIC = "fabric"
    TRACK = "track"
    DIFFUSER = "diffuser"
    MASKING = "masking"
    WOOD = "wood"
    FELT = "felt"
    OTHER = "other"


class AdditionalCostType(enum.StrEnum):
    LIFT_RENTAL = "lift_rental"
    TRAVEL_PER_DIEM = "travel_per_diem"
    TRAVEL_FLIGHTS = "travel_flights"
    TRAVEL_HOTELS = "travel_hotels"
    EQUIPMENT = "equipment"
    CONSUMABLES = "consumables"
    BOND = "bond"
    SITE_VISIT = "site_visit"
    PUNCH_LIST = "punch_list"
    SETUP_UNLOAD = "setup_unload"
    COMMISSION = "commission"
    OTHER = "other"


class EstimateStatus(enum.StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    FINALIZED = "finalized"
    EXPORTED = "exported"


class ExtractionStatus(enum.StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


# --- Helper column types ---

TIMESTAMPTZ = TIMESTAMP(timezone=True)


def pk_uuid() -> Any:
    """Return a new primary key UUID column (must be called per model, not shared)."""
    return mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


# --- Models ---


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = pk_uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    folder_name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    gc_name: Mapped[str | None] = mapped_column(Text)
    gc_contact: Mapped[str | None] = mapped_column(Text)
    project_type: Mapped[ProjectType | None] = mapped_column(
        Enum(ProjectType, name="project_type_enum", values_callable=lambda e: [x.value for x in e]),
    )
    quote_number: Mapped[str | None] = mapped_column(Text)
    quote_date: Mapped[date | None] = mapped_column(Date)
    bid_due_date: Mapped[date | None] = mapped_column(Date)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus | None] = mapped_column(
        Enum(
            ProjectStatus,
            name="project_status_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        server_default=text("'bid'"),
    )
    source_path: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    scopes: Mapped[list["Scope"]] = relationship(back_populates="project", cascade="all, delete")
    vendor_quotes: Mapped[list["VendorQuote"]] = relationship(back_populates="project", cascade="all, delete")
    additional_costs: Mapped[list["AdditionalCost"]] = relationship(back_populates="project", cascade="all, delete")
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(back_populates="project", cascade="all, delete")


class Scope(Base):
    __tablename__ = "scopes"

    id: Mapped[UUID] = pk_uuid()
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    tag: Mapped[str | None] = mapped_column(Text)
    scope_type: Mapped[ScopeType | None] = mapped_column(
        Enum(ScopeType, name="scope_type_enum", values_callable=lambda e: [x.value for x in e]),
    )
    product_name: Mapped[str | None] = mapped_column(Text)
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    square_footage: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    linear_footage: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    unit: Mapped[str | None] = mapped_column(String, server_default=text("'SF'"))
    cost_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    material_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    markup_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    material_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    man_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    daily_labor_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    labor_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    labor_base_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    labor_hours_per_day: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), server_default=text("8"))
    labor_multiplier: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    scrap_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    sales_tax_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), server_default=text("0.06"))
    county_surtax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    county_surtax_cap: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sales_tax: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    drawing_references: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    notes: Mapped[str | None] = mapped_column(Text)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    source_file: Mapped[str | None] = mapped_column(Text)
    source_sheet: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="scopes")
    product: Mapped[Optional["Product"]] = relationship(back_populates="scopes")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = pk_uuid()
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(Text)
    category: Mapped[ProductCategory | None] = mapped_column(
        Enum(
            ProductCategory,
            name="product_category_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
    )
    subcategory: Mapped[str | None] = mapped_column(Text)
    typical_cost_per_sf: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    typical_cost_per_lf: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    nrc_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    fire_rating: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    scopes: Mapped[list["Scope"]] = relationship(back_populates="product")
    estimate_scopes: Mapped[list["EstimateScope"]] = relationship(back_populates="product")


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[UUID] = pk_uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text)
    contact_name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    product_categories: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))

    # Relationships
    vendor_quotes: Mapped[list["VendorQuote"]] = relationship(back_populates="vendor")


class VendorQuote(Base):
    __tablename__ = "vendor_quotes"

    id: Mapped[UUID] = pk_uuid()
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    vendor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL"))
    quote_number: Mapped[str | None] = mapped_column(Text)
    quote_date: Mapped[date | None] = mapped_column(Date)
    items: Mapped[dict | None] = mapped_column(JSONB)
    freight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    sales_tax: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    lead_time: Mapped[str | None] = mapped_column(Text)
    source_file: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))

    # Relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="vendor_quotes")
    vendor: Mapped[Optional["Vendor"]] = relationship(back_populates="vendor_quotes")


class AdditionalCost(Base):
    __tablename__ = "additional_costs"

    id: Mapped[UUID] = pk_uuid()
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    cost_type: Mapped[AdditionalCostType | None] = mapped_column(
        Enum(
            AdditionalCostType,
            name="additional_cost_type_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
    )
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    source_file: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="additional_costs")


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[UUID] = pk_uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    project_address: Mapped[str | None] = mapped_column(Text)
    gc_name: Mapped[str | None] = mapped_column(Text)
    project_type: Mapped[ProjectType | None] = mapped_column(
        Enum(ProjectType, name="project_type_enum", values_callable=lambda e: [x.value for x in e]),
        use_existing_column=True,
    )
    source_plans: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    status: Mapped[EstimateStatus | None] = mapped_column(
        Enum(
            EstimateStatus,
            name="estimate_status_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        server_default=text("'draft'"),
    )
    total_estimate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    overall_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    created_by: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    estimate_scopes: Mapped[list["EstimateScope"]] = relationship(back_populates="estimate", cascade="all, delete")


class EstimateScope(Base):
    __tablename__ = "estimate_scopes"

    id: Mapped[UUID] = pk_uuid()
    estimate_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False
    )
    tag: Mapped[str | None] = mapped_column(Text)
    scope_type: Mapped[ScopeType | None] = mapped_column(
        Enum(ScopeType, name="scope_type_enum", values_callable=lambda e: [x.value for x in e]),
        use_existing_column=True,
    )
    product_name: Mapped[str | None] = mapped_column(Text)
    product_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL")
    )
    square_footage: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    linear_footage: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    unit: Mapped[str | None] = mapped_column(String, server_default=text("'SF'"))
    cost_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    material_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    markup_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    material_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    man_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    daily_labor_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    labor_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    labor_base_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    labor_hours_per_day: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), server_default=text("8"))
    labor_multiplier: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    scrap_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    sales_tax_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), server_default=text("0.06"))
    county_surtax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), server_default=text("0"))
    county_surtax_cap: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), server_default=text("5000"))
    sales_tax: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    comparable_project_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PG_UUID(as_uuid=True)))
    ai_notes: Mapped[str | None] = mapped_column(Text)
    room_name: Mapped[str | None] = mapped_column(Text)
    floor: Mapped[str | None] = mapped_column(Text)
    building: Mapped[str | None] = mapped_column(Text)
    drawing_reference: Mapped[str | None] = mapped_column(Text)
    manually_adjusted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    estimate: Mapped["Estimate"] = relationship(back_populates="estimate_scopes")
    product: Mapped[Optional["Product"]] = relationship(back_populates="estimate_scopes")


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[UUID] = pk_uuid()
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(
            ExtractionStatus,
            name="extraction_status_enum",
            values_callable=lambda e: [x.value for x in e],
        ),
        nullable=False,
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    error_message: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(Text)
    tokens_used: Mapped[int | None] = mapped_column(Integer)
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=text("CURRENT_TIMESTAMP"))

    # Relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="extraction_runs")
