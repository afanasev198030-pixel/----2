"""Extend deal_nature_code to 3 chars, add manufacturer/trademark/model/article to items.

Revision ID: 023
Revises: 022
"""
from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "declarations", "deal_nature_code",
        type_=sa.String(3),
        existing_type=sa.String(2),
        schema="core",
    )

    op.add_column("declaration_items", sa.Column("manufacturer", sa.String(300), nullable=True), schema="core")
    op.add_column("declaration_items", sa.Column("trademark", sa.String(200), nullable=True), schema="core")
    op.add_column("declaration_items", sa.Column("model_name", sa.String(200), nullable=True), schema="core")
    op.add_column("declaration_items", sa.Column("article_number", sa.String(100), nullable=True), schema="core")


def downgrade() -> None:
    op.drop_column("declaration_items", "article_number", schema="core")
    op.drop_column("declaration_items", "model_name", schema="core")
    op.drop_column("declaration_items", "trademark", schema="core")
    op.drop_column("declaration_items", "manufacturer", schema="core")

    op.alter_column(
        "declarations", "deal_nature_code",
        type_=sa.String(2),
        existing_type=sa.String(3),
        schema="core",
    )
