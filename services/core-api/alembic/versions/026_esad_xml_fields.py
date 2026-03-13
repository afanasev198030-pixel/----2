"""Add fields required for ESADout_CU XML export (FTS format 5.24.0).

Extends declaration_item_documents with doc_name, electronic archive refs,
and presenting details. Extends declarations with detailed signatory fields.

Revision ID: 026
Revises: 025
"""
from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── declaration_item_documents: ESADout_CU гр.44 fields ──
    op.add_column("declaration_item_documents",
                  sa.Column("doc_name", sa.String(250), nullable=True),
                  schema="core")
    op.add_column("declaration_item_documents",
                  sa.Column("record_id", sa.String(36), nullable=True),
                  schema="core")
    op.add_column("declaration_item_documents",
                  sa.Column("electronic_doc_id", sa.String(36), nullable=True),
                  schema="core")
    op.add_column("declaration_item_documents",
                  sa.Column("electronic_arch_id", sa.String(36), nullable=True),
                  schema="core")
    op.add_column("declaration_item_documents",
                  sa.Column("document_mode_id", sa.String(10), nullable=True),
                  schema="core")
    op.add_column("declaration_item_documents",
                  sa.Column("doc_begin_date", sa.Date, nullable=True),
                  schema="core")
    op.add_column("declaration_item_documents",
                  sa.Column("presenting_customs_code", sa.String(8), nullable=True),
                  schema="core")
    op.add_column("declaration_item_documents",
                  sa.Column("presenting_reg_date", sa.Date, nullable=True),
                  schema="core")
    op.add_column("declaration_item_documents",
                  sa.Column("presenting_gtd_number", sa.String(7), nullable=True),
                  schema="core")

    # ── declarations: detailed signatory & transport fields ──
    op.add_column("declarations",
                  sa.Column("signatory_surname", sa.String(100), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_first_name", sa.String(100), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_middle_name", sa.String(100), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_phone", sa.String(20), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_email", sa.String(100), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_id_card_code", sa.String(10), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_id_card_series", sa.String(10), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_id_card_number", sa.String(10), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_id_card_date", sa.Date, nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_id_card_org", sa.String(200), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_poa_number", sa.String(50), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_poa_date", sa.Date, nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_poa_start_date", sa.Date, nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_poa_end_date", sa.Date, nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("signatory_signing_date", sa.DateTime(timezone=True), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("broker_doc_kind_code", sa.String(5), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("broker_contract_doc_kind_code", sa.String(5), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("goods_location_info_type_code", sa.String(2), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("goods_location_svh_doc_id", sa.String(100), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("goods_location_address", sa.Text, nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("border_customs_name", sa.String(200), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("border_customs_country_code", sa.String(3), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("transport_kind_code", sa.String(3), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("transport_type_name", sa.String(200), nullable=True),
                  schema="core")
    op.add_column("declarations",
                  sa.Column("transport_means_quantity", sa.Integer, nullable=True),
                  schema="core")

    # ── declaration_items: ESADout_CU goods fields ──
    op.add_column("declaration_items",
                  sa.Column("goods_marking", sa.String(200), nullable=True),
                  schema="core")
    op.add_column("declaration_items",
                  sa.Column("serial_number", sa.String(200), nullable=True),
                  schema="core")
    op.add_column("declaration_items",
                  sa.Column("intellect_property_sign", sa.String(1), nullable=True),
                  schema="core")
    op.add_column("declaration_items",
                  sa.Column("goods_transfer_feature", sa.String(3), nullable=True),
                  schema="core")


def downgrade() -> None:
    for col in ("doc_name", "record_id", "electronic_doc_id", "electronic_arch_id",
                "document_mode_id", "doc_begin_date", "presenting_customs_code",
                "presenting_reg_date", "presenting_gtd_number"):
        op.drop_column("declaration_item_documents", col, schema="core")

    for col in ("signatory_surname", "signatory_first_name", "signatory_middle_name",
                "signatory_phone", "signatory_email",
                "signatory_id_card_code", "signatory_id_card_series",
                "signatory_id_card_number", "signatory_id_card_date", "signatory_id_card_org",
                "signatory_poa_number", "signatory_poa_date",
                "signatory_poa_start_date", "signatory_poa_end_date",
                "signatory_signing_date",
                "broker_doc_kind_code", "broker_contract_doc_kind_code",
                "goods_location_info_type_code", "goods_location_svh_doc_id",
                "goods_location_address",
                "border_customs_name", "border_customs_country_code",
                "transport_kind_code", "transport_type_name", "transport_means_quantity"):
        op.drop_column("declarations", col, schema="core")

    for col in ("goods_marking", "serial_number",
                "intellect_property_sign", "goods_transfer_feature"):
        op.drop_column("declaration_items", col, schema="core")
