"""Add missing DT fields: trading_country, declarant, transport, customs_post, documents_list

Revision ID: 004_dt_fields
Revises: 003_ml_feedback
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004_dt_fields"
down_revision = "003_ml_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Графа 11: Торговая страна
    op.add_column("declarations", sa.Column("trading_country_code", sa.String(2)), schema="core")
    # Графа 14: Декларант (отдельное поле, не counterparty)
    op.add_column("declarations", sa.Column("declarant_inn_kpp", sa.String(30)), schema="core")
    op.add_column("declarations", sa.Column("declarant_ogrn", sa.String(15)), schema="core")
    op.add_column("declarations", sa.Column("declarant_phone", sa.String(20)), schema="core")
    # Графа 20: Город поставки (после Incoterms)
    op.add_column("declarations", sa.Column("delivery_place", sa.String(200)), schema="core")
    # Графа 21: Транспорт на границе (номер рейса)
    op.add_column("declarations", sa.Column("transport_on_border_id", sa.String(100)), schema="core")
    # Графа 29: Орган въезда/выезда
    op.add_column("declarations", sa.Column("entry_customs_code", sa.String(8)), schema="core")
    # Графа 30: Местонахождение товаров (СВХ)
    op.add_column("declarations", sa.Column("goods_location", sa.Text), schema="core")
    # Графа 44: Документы (JSON список)
    op.add_column("declarations", sa.Column("attached_documents", JSONB), schema="core")
    # Графа 46: Статистическая стоимость
    op.add_column("declaration_items", sa.Column("statistical_value", sa.Numeric(15, 2)), schema="core")
    # Графа 36: Преференция (уже есть в модели, просто проверяем)
    # Графа 37: Процедура (уже есть)


def downgrade() -> None:
    op.drop_column("declarations", "trading_country_code", schema="core")
    op.drop_column("declarations", "declarant_inn_kpp", schema="core")
    op.drop_column("declarations", "declarant_ogrn", schema="core")
    op.drop_column("declarations", "declarant_phone", schema="core")
    op.drop_column("declarations", "delivery_place", schema="core")
    op.drop_column("declarations", "transport_on_border_id", schema="core")
    op.drop_column("declarations", "entry_customs_code", schema="core")
    op.drop_column("declarations", "goods_location", schema="core")
    op.drop_column("declarations", "attached_documents", schema="core")
    op.drop_column("declaration_items", "statistical_value", schema="core")
