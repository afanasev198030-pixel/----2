"""Add customs value declaration (DTS-1) tables.

Revision ID: 024
Revises: 023
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customs_value_declarations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("declaration_id", UUID(as_uuid=True), sa.ForeignKey("core.declarations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("form_type", sa.String(4), server_default="DTS1", nullable=False),
        # Графа 7
        sa.Column("related_parties", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("related_price_impact", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("related_verification", sa.Boolean, server_default=sa.text("false"), nullable=False),
        # Графа 8
        sa.Column("restrictions", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("price_conditions", sa.Boolean, server_default=sa.text("false"), nullable=False),
        # Графа 9
        sa.Column("ip_license_payments", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("sale_depends_on_income", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("income_to_seller", sa.Boolean, server_default=sa.text("false"), nullable=False),
        # Графа 6
        sa.Column("additional_docs", sa.Text, nullable=True),
        sa.Column("additional_data", sa.Text, nullable=True),
        # Графа 10б
        sa.Column("filler_name", sa.String(200), nullable=True),
        sa.Column("filler_date", sa.Date, nullable=True),
        sa.Column("filler_document", sa.String(200), nullable=True),
        sa.Column("filler_contacts", sa.String(200), nullable=True),
        sa.Column("filler_position", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="core",
    )

    op.create_table(
        "customs_value_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customs_value_declaration_id", UUID(as_uuid=True), sa.ForeignKey("core.customs_value_declarations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("declaration_item_id", UUID(as_uuid=True), sa.ForeignKey("core.declaration_items.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("item_no", sa.Integer, nullable=False),
        sa.Column("hs_code", sa.String(10), nullable=True),
        # Графа 11
        sa.Column("invoice_price_foreign", sa.DECIMAL(15, 2), nullable=True),
        sa.Column("invoice_price_national", sa.DECIMAL(15, 2), nullable=True),
        sa.Column("indirect_payments", sa.DECIMAL(15, 2), server_default="0"),
        # Графа 12
        sa.Column("base_total", sa.DECIMAL(15, 2), nullable=True),
        # Графы 13–19
        sa.Column("broker_commission", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("packaging_cost", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("raw_materials", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("tools_molds", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("consumed_materials", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("design_engineering", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("license_payments", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("seller_income", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("transport_cost", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("loading_unloading", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("insurance_cost", sa.DECIMAL(15, 2), server_default="0"),
        # Графа 20
        sa.Column("additions_total", sa.DECIMAL(15, 2), server_default="0"),
        # Графы 21–23
        sa.Column("construction_after_import", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("inland_transport", sa.DECIMAL(15, 2), server_default="0"),
        sa.Column("duties_taxes", sa.DECIMAL(15, 2), server_default="0"),
        # Графа 24
        sa.Column("deductions_total", sa.DECIMAL(15, 2), server_default="0"),
        # Графа 25
        sa.Column("customs_value_national", sa.DECIMAL(15, 2), nullable=True),
        sa.Column("customs_value_usd", sa.DECIMAL(15, 2), nullable=True),
        # Графа * — пересчёт валют
        sa.Column("currency_conversions", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="core",
    )

    op.create_index(
        "ix_customs_value_items_cvd_id",
        "customs_value_items",
        ["customs_value_declaration_id"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("ix_customs_value_items_cvd_id", table_name="customs_value_items", schema="core")
    op.drop_table("customs_value_items", schema="core")
    op.drop_table("customs_value_declarations", schema="core")
