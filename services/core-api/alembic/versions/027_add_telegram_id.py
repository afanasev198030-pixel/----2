"""add telegram_id to users

Revision ID: 027
Revises: 026
Create Date: 2026-03-12 20:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '027'
down_revision: Union[str, None] = '026'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add telegram_id column to core.users
    op.add_column('users', sa.Column('telegram_id', sa.String(length=50), nullable=True), schema='core')
    op.create_unique_constraint('uq_users_telegram_id', 'users', ['telegram_id'], schema='core')


def downgrade() -> None:
    # Remove telegram_id column from core.users
    op.drop_constraint('uq_users_telegram_id', 'users', schema='core', type_='unique')
    op.drop_column('users', 'telegram_id', schema='core')
