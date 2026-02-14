"""Add parse_issues table for batch testing error collection

Revision ID: 007_parse_issues
Revises: 006_hs_requirements
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "007_parse_issues"
down_revision = "006_hs_requirements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parse_issues",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("declaration_id", UUID(as_uuid=True), sa.ForeignKey("core.declarations.id"), nullable=True),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("resolved", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="core",
    )
    op.create_index("ix_parse_issues_stage", "parse_issues", ["stage"], schema="core")
    op.create_index("ix_parse_issues_severity", "parse_issues", ["severity"], schema="core")
    op.create_index("ix_parse_issues_created", "parse_issues", ["created_at"], schema="core")


def downgrade() -> None:
    op.drop_table("parse_issues", schema="core")
