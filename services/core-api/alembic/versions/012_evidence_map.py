"""Add evidence_map, ai_issues, ai_confidence to declarations + ParseIssue taxonomy fields

Revision ID: 012
Revises: 011
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import inspect

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('declarations', sa.Column('evidence_map', JSONB, nullable=True), schema='core')
    op.add_column('declarations', sa.Column('ai_issues', JSONB, nullable=True), schema='core')
    op.add_column('declarations', sa.Column('ai_confidence', sa.DECIMAL(3, 2), nullable=True), schema='core')

    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("parse_issues", schema="core")}

    if "code" not in columns:
        op.add_column('parse_issues', sa.Column('code', sa.String(50), nullable=True), schema='core')
    if "field" not in columns:
        op.add_column('parse_issues', sa.Column('field', sa.String(100), nullable=True), schema='core')
    if "blocking" not in columns:
        op.add_column('parse_issues', sa.Column('blocking', sa.Boolean, server_default='false'), schema='core')
    if "source" not in columns:
        op.add_column('parse_issues', sa.Column('source', sa.String(30), nullable=True), schema='core')

    indexes = {idx["name"] for idx in inspector.get_indexes("parse_issues", schema="core")}
    if 'ix_parse_issues_code' not in indexes:
        op.create_index('ix_parse_issues_code', 'parse_issues', ['code'], schema='core')
    if 'ix_parse_issues_blocking' not in indexes:
        op.create_index('ix_parse_issues_blocking', 'parse_issues', ['blocking'], schema='core')


def downgrade() -> None:
    op.drop_index('ix_parse_issues_blocking', table_name='parse_issues', schema='core')
    op.drop_index('ix_parse_issues_code', table_name='parse_issues', schema='core')
    op.drop_column('parse_issues', 'source', schema='core')
    op.drop_column('parse_issues', 'blocking', schema='core')
    op.drop_column('parse_issues', 'field', schema='core')
    op.drop_column('parse_issues', 'code', schema='core')

    op.drop_column('declarations', 'ai_confidence', schema='core')
    op.drop_column('declarations', 'ai_issues', schema='core')
    op.drop_column('declarations', 'evidence_map', schema='core')
