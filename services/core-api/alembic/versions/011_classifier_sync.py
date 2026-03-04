"""Add EEC sync fields to classifiers + classifier_sync_log table

Revision ID: 011
Revises: 010
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('classifiers', sa.Column('source', sa.String(20), server_default='seed'), schema='core')
    op.add_column('classifiers', sa.Column('eec_record_id', sa.Integer, nullable=True), schema='core')
    op.add_column('classifiers', sa.Column('start_date', sa.DateTime, nullable=True), schema='core')
    op.add_column('classifiers', sa.Column('end_date', sa.DateTime, nullable=True), schema='core')
    op.create_index('idx_classifier_source', 'classifiers', ['source'], schema='core')

    op.create_table(
        'classifier_sync_log',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('classifier_type', sa.String(50), nullable=False),
        sa.Column('eec_guid', sa.String(40), nullable=False),
        sa.Column('last_sync_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('last_modification_check', sa.Date, nullable=True),
        sa.Column('records_total', sa.Integer, server_default='0'),
        sa.Column('records_updated', sa.Integer, server_default='0'),
        sa.Column('status', sa.String(20), server_default="'pending'"),
        sa.Column('error_message', sa.Text, nullable=True),
        schema='core',
    )
    op.create_index(
        'ix_sync_log_type', 'classifier_sync_log', ['classifier_type'], schema='core'
    )


def downgrade() -> None:
    op.drop_index('ix_sync_log_type', table_name='classifier_sync_log', schema='core')
    op.drop_table('classifier_sync_log', schema='core')
    op.drop_index('idx_classifier_source', table_name='classifiers', schema='core')
    op.drop_column('classifiers', 'end_date', schema='core')
    op.drop_column('classifiers', 'start_date', schema='core')
    op.drop_column('classifiers', 'eec_record_id', schema='core')
    op.drop_column('classifiers', 'source', schema='core')
