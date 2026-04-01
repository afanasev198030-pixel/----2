"""Expand commercial_name column from VARCHAR(500) to TEXT.

Full product description from technical descriptions can exceed 500 chars.
"""
from alembic import op
import sqlalchemy as sa


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "declaration_items",
        "commercial_name",
        type_=sa.Text(),
        existing_type=sa.String(500),
        schema="core",
    )


def downgrade():
    op.alter_column(
        "declaration_items",
        "commercial_name",
        type_=sa.String(500),
        existing_type=sa.Text(),
        schema="core",
    )
