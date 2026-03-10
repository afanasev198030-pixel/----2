"""Add declaration fields for графа 10 and графа 52

country_first_destination_code (графа 10) — страна первого назначения
guarantee_info (графа 52) — гарантия недействительна для

Revision ID: 020
Revises: 019
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('declarations', schema='core')}
    if 'country_first_destination_code' not in cols:
        op.add_column('declarations', sa.Column('country_first_destination_code', sa.String(2), nullable=True), schema='core')
    if 'guarantee_info' not in cols:
        op.add_column('declarations', sa.Column('guarantee_info', sa.String(500), nullable=True), schema='core')


def downgrade() -> None:
    op.drop_column('declarations', 'guarantee_info', schema='core')
    op.drop_column('declarations', 'country_first_destination_code', schema='core')
