"""ai_usage_log — track AI token usage and costs per declaration

Revision ID: 016
Revises: 015
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_usage_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', UUID(as_uuid=True), nullable=True),
        sa.Column('declaration_id', UUID(as_uuid=True), nullable=True),
        sa.Column('operation', sa.String(50), nullable=False),
        sa.Column('model', sa.String(50), nullable=False),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('input_tokens', sa.Integer, server_default='0'),
        sa.Column('output_tokens', sa.Integer, server_default='0'),
        sa.Column('total_tokens', sa.Integer, server_default='0'),
        sa.Column('cost_usd', sa.DECIMAL(10, 6), nullable=True),
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='core',
    )
    op.create_index('ix_ai_usage_company', 'ai_usage_log', ['company_id'], schema='core')
    op.create_index('ix_ai_usage_declaration', 'ai_usage_log', ['declaration_id'], schema='core')
    op.create_index('ix_ai_usage_created', 'ai_usage_log', ['created_at'], schema='core')


def downgrade() -> None:
    op.drop_index('ix_ai_usage_created', table_name='ai_usage_log', schema='core')
    op.drop_index('ix_ai_usage_declaration', table_name='ai_usage_log', schema='core')
    op.drop_index('ix_ai_usage_company', table_name='ai_usage_log', schema='core')
    op.drop_table('ai_usage_log', schema='core')
