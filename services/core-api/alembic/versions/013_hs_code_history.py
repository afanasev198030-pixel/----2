"""hs_code_history — track HS codes by counterparty for auto-fill

Revision ID: 013
Revises: 012
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'hs_code_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('company_id', UUID(as_uuid=True), sa.ForeignKey('core.companies.id'), nullable=False),
        sa.Column('counterparty_id', UUID(as_uuid=True), sa.ForeignKey('core.counterparties.id'), nullable=True),
        sa.Column('counterparty_name', sa.String(500), nullable=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('description_trgm', sa.String(300), nullable=True),
        sa.Column('hs_code', sa.String(10), nullable=False),
        sa.Column('declaration_id', UUID(as_uuid=True), sa.ForeignKey('core.declarations.id'), nullable=True),
        sa.Column('item_id', UUID(as_uuid=True), nullable=True),
        sa.Column('source', sa.String(20), server_default='ai'),
        sa.Column('confirmed_by', UUID(as_uuid=True), nullable=True),
        sa.Column('usage_count', sa.Integer, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='core',
    )
    op.create_index('ix_hsh_company_desc', 'hs_code_history', ['company_id', 'description_trgm'], schema='core')
    op.create_index('ix_hsh_counterparty', 'hs_code_history', ['counterparty_id'], schema='core')
    op.create_index('ix_hsh_hs_code', 'hs_code_history', ['hs_code'], schema='core')

    op.execute("CREATE INDEX IF NOT EXISTS ix_hsh_trgm ON core.hs_code_history USING gin (description_trgm gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS core.ix_hsh_trgm")
    op.drop_index('ix_hsh_hs_code', table_name='hs_code_history', schema='core')
    op.drop_index('ix_hsh_counterparty', table_name='hs_code_history', schema='core')
    op.drop_index('ix_hsh_company_desc', table_name='hs_code_history', schema='core')
    op.drop_table('hs_code_history', schema='core')
