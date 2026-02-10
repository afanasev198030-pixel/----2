"""Add broker/multi-company support: company_type, broker_clients, user_company_access

Revision ID: 005_broker_clients
Revises: 004_dt_fields
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005_broker_clients"
down_revision = "004_dt_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to companies
    op.add_column(
        "companies",
        sa.Column("company_type", sa.String(20), server_default="client"),
        schema="core",
    )
    op.add_column(
        "companies",
        sa.Column("broker_license", sa.String(50), nullable=True),
        schema="core",
    )
    op.add_column(
        "companies",
        sa.Column("contact_email", sa.String(255), nullable=True),
        schema="core",
    )
    op.add_column(
        "companies",
        sa.Column("contact_phone", sa.String(30), nullable=True),
        schema="core",
    )

    # Create broker_clients table
    op.create_table(
        "broker_clients",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "broker_company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.companies.id"),
            nullable=False,
        ),
        sa.Column(
            "client_company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.companies.id"),
            nullable=False,
        ),
        sa.Column("contract_number", sa.String(100), nullable=True),
        sa.Column("contract_date", sa.Date, nullable=True),
        sa.Column("tariff_plan", sa.String(50), server_default="standard"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "broker_company_id", "client_company_id", name="uq_broker_client"
        ),
        schema="core",
    )

    # Create user_company_access table
    op.create_table(
        "user_company_access",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.users.id"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("core.companies.id"),
            nullable=False,
        ),
        sa.Column("access_level", sa.String(20), server_default="full"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_company"),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("user_company_access", schema="core")
    op.drop_table("broker_clients", schema="core")
    op.drop_column("companies", "contact_phone", schema="core")
    op.drop_column("companies", "contact_email", schema="core")
    op.drop_column("companies", "broker_license", schema="core")
    op.drop_column("companies", "company_type", schema="core")
