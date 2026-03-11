"""FTS XML data model: extend counterparty, declaration, items; add item_documents and preceding_docs tables.

Revision ID: 022
Revises: 021
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Counterparty: add structured address & identifiers ---
    op.add_column("counterparties", sa.Column("ogrn", sa.String(15)), schema="core")
    op.add_column("counterparties", sa.Column("kpp", sa.String(9)), schema="core")
    op.add_column("counterparties", sa.Column("postal_code", sa.String(6)), schema="core")
    op.add_column("counterparties", sa.Column("region", sa.String(100)), schema="core")
    op.add_column("counterparties", sa.Column("city", sa.String(100)), schema="core")
    op.add_column("counterparties", sa.Column("street", sa.String(200)), schema="core")
    op.add_column("counterparties", sa.Column("building", sa.String(20)), schema="core")
    op.add_column("counterparties", sa.Column("room", sa.String(20)), schema="core")
    op.add_column("counterparties", sa.Column("phone", sa.String(30)), schema="core")
    op.add_column("counterparties", sa.Column("email", sa.String(100)), schema="core")

    # --- Declaration: signatory, broker, transport, goods location ---
    op.add_column("declarations", sa.Column("signatory_name", sa.String(200)), schema="core")
    op.add_column("declarations", sa.Column("signatory_position", sa.String(200)), schema="core")
    op.add_column("declarations", sa.Column("signatory_id_doc", sa.String(200)), schema="core")
    op.add_column("declarations", sa.Column("signatory_cert_number", sa.String(20)), schema="core")
    op.add_column("declarations", sa.Column("signatory_power_of_attorney", sa.String(200)), schema="core")
    op.add_column("declarations", sa.Column("broker_registry_number", sa.String(30)), schema="core")
    op.add_column("declarations", sa.Column("broker_contract_number", sa.String(50)), schema="core")
    op.add_column("declarations", sa.Column("broker_contract_date", sa.DateTime), schema="core")
    op.add_column("declarations", sa.Column("transport_reg_number", sa.String(50)), schema="core")
    op.add_column("declarations", sa.Column("transport_nationality_code", sa.String(2)), schema="core")
    op.add_column("declarations", sa.Column("goods_location_code", sa.String(2)), schema="core")
    op.add_column("declarations", sa.Column("goods_location_customs_code", sa.String(8)), schema="core")
    op.add_column("declarations", sa.Column("goods_location_zone_id", sa.String(50)), schema="core")

    # --- DeclarationItem: package & unit extensions ---
    op.add_column("declaration_items", sa.Column("package_type_code", sa.String(5)), schema="core")
    op.add_column("declaration_items", sa.Column("package_marks", sa.String(500)), schema="core")
    op.add_column("declaration_items", sa.Column("additional_unit_code", sa.String(4)), schema="core")

    # --- CustomsPayment: FTS rate detail fields ---
    op.add_column("customs_payments", sa.Column("tax_base_currency_code", sa.String(3)), schema="core")
    op.add_column("customs_payments", sa.Column("tax_base_unit_code", sa.String(4)), schema="core")
    op.add_column("customs_payments", sa.Column("rate_type_code", sa.String(1)), schema="core")
    op.add_column("customs_payments", sa.Column("rate_currency_code", sa.String(3)), schema="core")
    op.add_column("customs_payments", sa.Column("rate_unit_code", sa.String(4)), schema="core")
    op.add_column("customs_payments", sa.Column("weighting_factor", sa.DECIMAL(19, 6)), schema="core")
    op.add_column("customs_payments", sa.Column("rate_use_date", sa.Date), schema="core")

    # --- New table: declaration_item_documents (графа 44) ---
    op.create_table(
        "declaration_item_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("declaration_item_id", UUID(as_uuid=True), sa.ForeignKey("core.declaration_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_kind_code", sa.String(5), nullable=False),
        sa.Column("doc_number", sa.String(50)),
        sa.Column("doc_date", sa.Date),
        sa.Column("doc_validity_date", sa.Date),
        sa.Column("authority_name", sa.String(300)),
        sa.Column("country_code", sa.String(2)),
        sa.Column("edoc_code", sa.String(10)),
        sa.Column("archive_doc_id", sa.String(36)),
        sa.Column("line_id", sa.String(40)),
        sa.Column("presenting_kind_code", sa.String(1)),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="core",
    )
    op.create_index(
        "idx_item_documents_item_id",
        "declaration_item_documents",
        ["declaration_item_id"],
        schema="core",
    )

    # --- New table: declaration_item_preceding_docs (графа 40) ---
    op.create_table(
        "declaration_item_preceding_docs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("declaration_item_id", UUID(as_uuid=True), sa.ForeignKey("core.declaration_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_kind_code", sa.String(5)),
        sa.Column("doc_name", sa.String(250)),
        sa.Column("customs_office_code", sa.String(8)),
        sa.Column("doc_date", sa.Date),
        sa.Column("customs_doc_number", sa.String(7)),
        sa.Column("other_doc_number", sa.String(50)),
        sa.Column("other_doc_date", sa.Date),
        sa.Column("goods_number", sa.Integer),
        sa.Column("line_id", sa.String(40)),
        sa.Column("sort_order", sa.Integer, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="core",
    )
    op.create_index(
        "idx_item_preceding_docs_item_id",
        "declaration_item_preceding_docs",
        ["declaration_item_id"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("declaration_item_preceding_docs", schema="core")
    op.drop_table("declaration_item_documents", schema="core")

    for col in ("tax_base_currency_code", "tax_base_unit_code", "rate_type_code",
                "rate_currency_code", "rate_unit_code", "weighting_factor", "rate_use_date"):
        op.drop_column("customs_payments", col, schema="core")

    for col in ("package_type_code", "package_marks", "additional_unit_code"):
        op.drop_column("declaration_items", col, schema="core")

    for col in ("signatory_name", "signatory_position", "signatory_id_doc",
                "signatory_cert_number", "signatory_power_of_attorney",
                "broker_registry_number", "broker_contract_number", "broker_contract_date",
                "transport_reg_number", "transport_nationality_code",
                "goods_location_code", "goods_location_customs_code", "goods_location_zone_id"):
        op.drop_column("declarations", col, schema="core")

    for col in ("ogrn", "kpp", "postal_code", "region", "city", "street", "building", "room", "phone", "email"):
        op.drop_column("counterparties", col, schema="core")
