"""Add freight_amount and freight_currency to declarations

Revision ID: 008_freight
Revises: 007_parse_issues
"""
from alembic import op
import sqlalchemy as sa

revision = "008_freight"
down_revision = "007_parse_issues"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("declarations", sa.Column("freight_amount", sa.DECIMAL(15, 2), nullable=True), schema="core")
    op.add_column("declarations", sa.Column("freight_currency", sa.String(3), nullable=True), schema="core")


def downgrade() -> None:
    op.drop_column("declarations", "freight_currency", schema="core")
    op.drop_column("declarations", "freight_amount", schema="core")
