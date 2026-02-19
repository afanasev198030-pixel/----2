"""knowledge articles and checklists

Revision ID: 009
Revises: 008
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'knowledge_articles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text, nullable=False, server_default=''),
        sa.Column('category', sa.String(100), nullable=False, server_default='general'),
        sa.Column('tags', JSONB, server_default='[]'),
        sa.Column('hs_codes', JSONB, server_default='[]'),
        sa.Column('is_published', sa.Boolean, server_default='false'),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('core.users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()')),
        schema='core',
    )
    op.create_index('ix_knowledge_category', 'knowledge_articles', ['category'], schema='core')

    op.create_table(
        'checklists',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(300), nullable=False),
        sa.Column('description', sa.Text, server_default=''),
        sa.Column('declaration_type', sa.String(10), server_default='IM40'),
        sa.Column('items', JSONB, server_default='[]'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('core.users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()')),
        schema='core',
    )


def downgrade() -> None:
    op.drop_table('checklists', schema='core')
    op.drop_index('ix_knowledge_category', table_name='knowledge_articles', schema='core')
    op.drop_table('knowledge_articles', schema='core')
