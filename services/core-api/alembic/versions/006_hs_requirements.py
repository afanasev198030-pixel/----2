"""Add hs_requirements table for certificate/license/permit requirements by HS code

Revision ID: 006_hs_requirements
Revises: 005_broker_clients
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006_hs_requirements"
down_revision = "005_broker_clients"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hs_requirements",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column("hs_code_prefix", sa.String(10), nullable=False),
        sa.Column("requirement_type", sa.String(30), nullable=False),
        sa.Column("document_name", sa.String(500), nullable=False),
        sa.Column("issuing_authority", sa.String(500), nullable=True),
        sa.Column("legal_basis", sa.String(500), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        schema="core",
    )

    op.create_index(
        "idx_hs_requirements_prefix",
        "hs_requirements",
        ["hs_code_prefix"],
        schema="core",
    )

    op.create_index(
        "idx_hs_requirements_type",
        "hs_requirements",
        ["requirement_type"],
        schema="core",
    )


def downgrade() -> None:
    op.drop_index("idx_hs_requirements_type", table_name="hs_requirements", schema="core")
    op.drop_index("idx_hs_requirements_prefix", table_name="hs_requirements", schema="core")
    op.drop_table("hs_requirements", schema="core")
