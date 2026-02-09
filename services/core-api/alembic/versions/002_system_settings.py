"""Add system_settings table

Revision ID: 002_system_settings
Revises: 001_initial
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa

revision = "002_system_settings"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("system_settings", schema="core")
