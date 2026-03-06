"""Add declaration fields for графа 10 and графа 52

country_first_destination_code (графа 10) — страна первого назначения
guarantee_info (графа 52) — гарантия недействительна для

Revision ID: 017
Revises: 016
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('declarations', sa.Column('country_first_destination_code', sa.String(2), nullable=True), schema='core')
    op.add_column('declarations', sa.Column('guarantee_info', sa.String(500), nullable=True), schema='core')


def downgrade() -> None:
    op.drop_column('declarations', 'guarantee_info', schema='core')
    op.drop_column('declarations', 'country_first_destination_code', schema='core')
