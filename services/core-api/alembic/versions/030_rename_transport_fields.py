"""Rename transport fields to semantic names + add new columns.

transport_at_border -> departure_vehicle_info (гр. 18)
transport_nationality_code -> departure_vehicle_country (гр. 18)
transport_on_border_id -> border_vehicle_info (гр. 21)
+ border_vehicle_country (гр. 21) — new
+ transport_doc_number (AWB/CMR) — new
"""
from alembic import op
import sqlalchemy as sa


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "declarations", "transport_at_border",
        new_column_name="departure_vehicle_info", schema="core",
    )
    op.alter_column(
        "declarations", "transport_nationality_code",
        new_column_name="departure_vehicle_country", schema="core",
    )
    op.alter_column(
        "declarations", "transport_on_border_id",
        new_column_name="border_vehicle_info", schema="core",
    )
    op.add_column(
        "declarations",
        sa.Column("border_vehicle_country", sa.String(2), nullable=True),
        schema="core",
    )
    op.add_column(
        "declarations",
        sa.Column("transport_doc_number", sa.String(100), nullable=True),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("declarations", "transport_doc_number", schema="core")
    op.drop_column("declarations", "border_vehicle_country", schema="core")
    op.alter_column(
        "declarations", "border_vehicle_info",
        new_column_name="transport_on_border_id", schema="core",
    )
    op.alter_column(
        "declarations", "departure_vehicle_country",
        new_column_name="transport_nationality_code", schema="core",
    )
    op.alter_column(
        "declarations", "departure_vehicle_info",
        new_column_name="transport_at_border", schema="core",
    )
