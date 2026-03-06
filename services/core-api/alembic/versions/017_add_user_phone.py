"""add phone column to core.users

Revision ID: 017
Revises: 016
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users", schema="core")}
    if "phone" not in columns:
        op.add_column("users", sa.Column("phone", sa.String(30), nullable=True), schema="core")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users", schema="core")}
    if "phone" in columns:
        op.drop_column("users", "phone", schema="core")
