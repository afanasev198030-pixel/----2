"""Increase classifiers.name_ru from varchar(500) to varchar(2000)

Some EEC classifier names exceed 500 characters (e.g. doc_type, preference, tax_type).

Revision ID: 012
Revises: 011
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'classifiers', 'name_ru',
        type_=sa.String(2000),
        existing_type=sa.String(500),
        schema='core',
    )


def downgrade() -> None:
    op.alter_column(
        'classifiers', 'name_ru',
        type_=sa.String(500),
        existing_type=sa.String(2000),
        schema='core',
    )
