"""add ai_task_id and processing_status to declarations

Revision ID: 028
Revises: 027
Create Date: 2026-03-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '028'
down_revision: Union[str, None] = '027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'core' AND table_name = 'declarations' AND column_name = 'ai_task_id'"
    ))
    if result.fetchone() is None:
        op.add_column('declarations', sa.Column('ai_task_id', sa.String(length=100), nullable=True), schema='core')

    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'core' AND table_name = 'declarations' AND column_name = 'processing_status'"
    ))
    if result.fetchone() is None:
        op.add_column('declarations', sa.Column('processing_status', sa.String(length=20), nullable=True), schema='core')


def downgrade() -> None:
    op.drop_column('declarations', 'processing_status', schema='core')
    op.drop_column('declarations', 'ai_task_id', schema='core')
