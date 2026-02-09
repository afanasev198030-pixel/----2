"""Initial migration - all core tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-02-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure schemas exist
    op.execute("CREATE SCHEMA IF NOT EXISTS core")
    op.execute("CREATE SCHEMA IF NOT EXISTS ai")
    op.execute("CREATE SCHEMA IF NOT EXISTS integration")
    op.execute("CREATE SCHEMA IF NOT EXISTS calc")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # --- companies ---
    op.create_table(
        "companies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("inn", sa.String(12), unique=True),
        sa.Column("kpp", sa.String(9)),
        sa.Column("ogrn", sa.String(15)),
        sa.Column("address", sa.Text),
        sa.Column("country_code", sa.String(2)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("role", sa.String(50), nullable=False, server_default="ved_specialist"),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("core.companies.id")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )

    # --- counterparties ---
    op.create_table(
        "counterparties",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("country_code", sa.String(2)),
        sa.Column("registration_number", sa.String(100)),
        sa.Column("tax_number", sa.String(50)),
        sa.Column("address", sa.Text),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("core.companies.id")),
        schema="core",
    )

    # --- declarations ---
    op.create_table(
        "declarations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("number_internal", sa.String(50)),
        sa.Column("type_code", sa.String(10)),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("core.companies.id")),
        sa.Column("sender_counterparty_id", UUID(as_uuid=True), sa.ForeignKey("core.counterparties.id")),
        sa.Column("receiver_counterparty_id", UUID(as_uuid=True), sa.ForeignKey("core.counterparties.id")),
        sa.Column("financial_counterparty_id", UUID(as_uuid=True), sa.ForeignKey("core.counterparties.id")),
        sa.Column("declarant_counterparty_id", UUID(as_uuid=True), sa.ForeignKey("core.counterparties.id")),
        sa.Column("country_dispatch_code", sa.String(2)),
        sa.Column("country_origin_code", sa.String(2)),
        sa.Column("country_destination_code", sa.String(2)),
        sa.Column("transport_at_border", sa.String(100)),
        sa.Column("container_info", sa.String(200)),
        sa.Column("incoterms_code", sa.String(3)),
        sa.Column("transport_on_border", sa.String(100)),
        sa.Column("currency_code", sa.String(3)),
        sa.Column("total_invoice_value", sa.Numeric(15, 2)),
        sa.Column("exchange_rate", sa.Numeric(15, 6)),
        sa.Column("deal_nature_code", sa.String(2)),
        sa.Column("transport_type_border", sa.String(2)),
        sa.Column("transport_type_inland", sa.String(2)),
        sa.Column("loading_place", sa.String(200)),
        sa.Column("financial_info", sa.Text),
        sa.Column("total_customs_value", sa.Numeric(15, 2)),
        sa.Column("total_gross_weight", sa.Numeric(12, 3)),
        sa.Column("total_net_weight", sa.Numeric(12, 3)),
        sa.Column("total_items_count", sa.Integer),
        sa.Column("total_packages_count", sa.Integer),
        sa.Column("forms_count", sa.Integer),
        sa.Column("specifications_count", sa.Integer),
        sa.Column("customs_office_code", sa.String(8)),
        sa.Column("warehouse_name", sa.String(200)),
        sa.Column("spot_required", sa.Boolean, server_default=sa.text("false")),
        sa.Column("spot_status", sa.String(50), server_default="none"),
        sa.Column("spot_qr_file_key", sa.String(500)),
        sa.Column("spot_amount", sa.Numeric(15, 2)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("place_and_date", sa.String(200)),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("core.users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )

    # --- declaration_items ---
    op.create_table(
        "declaration_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("declaration_id", UUID(as_uuid=True), sa.ForeignKey("core.declarations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_no", sa.Integer),
        sa.Column("description", sa.Text),
        sa.Column("package_count", sa.Integer),
        sa.Column("package_type", sa.String(50)),
        sa.Column("commercial_name", sa.String(500)),
        sa.Column("hs_code", sa.String(10)),
        sa.Column("country_origin_code", sa.String(2)),
        sa.Column("gross_weight", sa.Numeric(12, 3)),
        sa.Column("preference_code", sa.String(10)),
        sa.Column("procedure_code", sa.String(10)),
        sa.Column("net_weight", sa.Numeric(12, 3)),
        sa.Column("quota_info", sa.String(200)),
        sa.Column("prev_doc_ref", sa.String(200)),
        sa.Column("additional_unit", sa.String(20)),
        sa.Column("additional_unit_qty", sa.Numeric(12, 3)),
        sa.Column("unit_price", sa.Numeric(15, 4)),
        sa.Column("mos_method_code", sa.String(2)),
        sa.Column("customs_value_rub", sa.Numeric(15, 2)),
        sa.Column("risk_score", sa.Integer, server_default=sa.text("0")),
        sa.Column("risk_flags", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("declaration_id", UUID(as_uuid=True), sa.ForeignKey("core.declarations.id", ondelete="SET NULL")),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("core.declaration_items.id", ondelete="SET NULL")),
        sa.Column("doc_type", sa.String(50)),
        sa.Column("file_key", sa.String(500)),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("file_size", sa.BigInteger),
        sa.Column("issued_at", sa.Date),
        sa.Column("issuer", sa.String(255)),
        sa.Column("doc_number", sa.String(100)),
        sa.Column("parsed_data", JSONB),
        sa.Column("linked_fields", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )

    # --- classifiers ---
    op.create_table(
        "classifiers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("classifier_type", sa.String(50), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name_ru", sa.String(500)),
        sa.Column("name_en", sa.String(500)),
        sa.Column("parent_code", sa.String(20)),
        sa.Column("meta", JSONB),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        schema="core",
    )
    op.create_index(
        "ix_classifiers_type_code",
        "classifiers",
        ["classifier_type", "code"],
        unique=True,
        schema="core",
    )

    # --- customs_payments ---
    op.create_table(
        "customs_payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("declaration_id", UUID(as_uuid=True), sa.ForeignKey("core.declarations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("core.declaration_items.id", ondelete="SET NULL")),
        sa.Column("payment_type", sa.String(50)),
        sa.Column("base_amount", sa.Numeric(15, 2)),
        sa.Column("rate", sa.Numeric(10, 4)),
        sa.Column("amount", sa.Numeric(15, 2)),
        sa.Column("currency_code", sa.String(3)),
        sa.Column("calc_details", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )

    # --- declaration_logs ---
    op.create_table(
        "declaration_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("declaration_id", UUID(as_uuid=True), sa.ForeignKey("core.declarations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("core.users.id")),
        sa.Column("action", sa.String(50)),
        sa.Column("old_value", JSONB),
        sa.Column("new_value", JSONB),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )

    # --- declaration_status_history ---
    op.create_table(
        "declaration_status_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("declaration_id", UUID(as_uuid=True), sa.ForeignKey("core.declarations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status_code", sa.String(50)),
        sa.Column("status_text", sa.Text),
        sa.Column("source", sa.String(50)),
        sa.Column("customs_post_code", sa.String(8)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("declaration_status_history", schema="core")
    op.drop_table("declaration_logs", schema="core")
    op.drop_table("customs_payments", schema="core")
    op.drop_index("ix_classifiers_type_code", table_name="classifiers", schema="core")
    op.drop_table("classifiers", schema="core")
    op.drop_table("documents", schema="core")
    op.drop_table("declaration_items", schema="core")
    op.drop_table("declarations", schema="core")
    op.drop_table("counterparties", schema="core")
    op.drop_table("users", schema="core")
    op.drop_table("companies", schema="core")
