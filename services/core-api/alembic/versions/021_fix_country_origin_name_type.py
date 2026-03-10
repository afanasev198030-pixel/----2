"""Fix country_origin_name column type VARCHAR(2) -> VARCHAR(60)

Migration 019 renamed country_origin_code to country_origin_name
but failed to widen the type due to a stale inspector snapshot.

Revision ID: 021
Revises: 020
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE core.declarations "
        "ALTER COLUMN country_origin_name TYPE VARCHAR(60)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE core.declarations "
        "ALTER COLUMN country_origin_name TYPE VARCHAR(2)"
    )
