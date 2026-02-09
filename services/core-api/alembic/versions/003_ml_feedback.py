"""Add ml_feedback table for DSPy auto-optimization

Revision ID: 003_ml_feedback
Revises: 002_system_settings
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "003_ml_feedback"
down_revision = "002_system_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ml_feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("declaration_id", UUID(as_uuid=True)),
        sa.Column("item_id", UUID(as_uuid=True)),
        sa.Column("feedback_type", sa.String(30)),
        sa.Column("predicted_value", sa.Text),
        sa.Column("actual_value", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("metadata", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("ml_feedback", schema="core")
