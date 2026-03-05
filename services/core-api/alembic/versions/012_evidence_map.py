"""Add evidence_map, ai_issues, ai_confidence to declarations + ParseIssue taxonomy fields

Revision ID: 012
Revises: 011
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('declarations', sa.Column('evidence_map', JSONB, nullable=True), schema='core')
    op.add_column('declarations', sa.Column('ai_issues', JSONB, nullable=True), schema='core')
    op.add_column('declarations', sa.Column('ai_confidence', sa.DECIMAL(3, 2), nullable=True), schema='core')

    from sqlalchemy.dialects.postgresql import UUID
    op.create_table(
        'parse_issues',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('declaration_id', UUID(as_uuid=True), sa.ForeignKey('core.declarations.id'), nullable=True),
        sa.Column('stage', sa.String(30), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('code', sa.String(50), nullable=True),
        sa.Column('field', sa.String(100), nullable=True),
        sa.Column('blocking', sa.Boolean, server_default='false'),
        sa.Column('source', sa.String(30), nullable=True),
        sa.Column('message', sa.Text, nullable=False),
        sa.Column('details', JSONB, nullable=True),
        sa.Column('resolved', sa.Boolean, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='core',
    )
    op.create_index('ix_parse_issues_code', 'parse_issues', ['code'], schema='core')
    op.create_index('ix_parse_issues_blocking', 'parse_issues', ['blocking'], schema='core')


def downgrade() -> None:
    op.drop_index('ix_parse_issues_blocking', table_name='parse_issues', schema='core')
    op.drop_index('ix_parse_issues_code', table_name='parse_issues', schema='core')
    op.drop_table('parse_issues', schema='core')

    op.drop_column('declarations', 'ai_confidence', schema='core')
    op.drop_column('declarations', 'ai_issues', schema='core')
    op.drop_column('declarations', 'evidence_map', schema='core')
