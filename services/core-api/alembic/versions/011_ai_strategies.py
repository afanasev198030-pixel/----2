"""ai_strategies — business rules for AI declaration filling

Revision ID: 011
Revises: 010
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_strategies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(300), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('rule_text', sa.Text, nullable=False),
        sa.Column('conditions', JSONB, nullable=True),
        sa.Column('actions', JSONB, nullable=True),
        sa.Column('priority', sa.Integer, server_default='0'),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_by', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='core',
    )
    op.create_index('ix_ai_strategies_active', 'ai_strategies', ['is_active'], schema='core')
    op.create_index('ix_ai_strategies_priority', 'ai_strategies', ['priority'], schema='core')


def downgrade() -> None:
    op.drop_index('ix_ai_strategies_priority', table_name='ai_strategies', schema='core')
    op.drop_index('ix_ai_strategies_active', table_name='ai_strategies', schema='core')
    op.drop_table('ai_strategies', schema='core')
