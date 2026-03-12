"""DTS fixes: invoice/contract for гр.4-5, transport carrier for гр.17, usd rate.

Revision ID: 025
Revises: 024
"""
from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Declarations: invoice/contract for ДТС графы 4, 5
    op.add_column(
        "declarations",
        sa.Column("invoice_number", sa.String(100), nullable=True),
        schema="core",
    )
    op.add_column(
        "declarations",
        sa.Column("invoice_date", sa.Date, nullable=True),
        schema="core",
    )
    op.add_column(
        "declarations",
        sa.Column("contract_number", sa.String(100), nullable=True),
        schema="core",
    )
    op.add_column(
        "declarations",
        sa.Column("contract_date", sa.Date, nullable=True),
        schema="core",
    )

    # CustomsValueDeclaration: перевозчик (гр.17), место "до", курс USD (гр.25б)
    op.add_column(
        "customs_value_declarations",
        sa.Column("transport_carrier_name", sa.String(200), nullable=True),
        schema="core",
    )
    op.add_column(
        "customs_value_declarations",
        sa.Column("transport_destination", sa.String(200), nullable=True),
        schema="core",
    )
    op.add_column(
        "customs_value_declarations",
        sa.Column("usd_exchange_rate", sa.Numeric(15, 6), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("customs_value_declarations", "usd_exchange_rate", schema="core")
    op.drop_column("customs_value_declarations", "transport_destination", schema="core")
    op.drop_column("customs_value_declarations", "transport_carrier_name", schema="core")
    op.drop_column("declarations", "contract_date", schema="core")
    op.drop_column("declarations", "contract_number", schema="core")
    op.drop_column("declarations", "invoice_date", schema="core")
    op.drop_column("declarations", "invoice_number", schema="core")
