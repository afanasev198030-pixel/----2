"""declaration_graph_rules — per-graph filling rules in DB

Revision ID: 010
Revises: 009
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'declaration_graph_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Идентификаторы графы
        sa.Column('graph_number', sa.Integer, nullable=False),
        sa.Column('graph_name', sa.String(300), nullable=False),
        # Раздел: header / item / payment / other
        sa.Column('section', sa.String(30), nullable=False, server_default='header'),
        # Тип декларации: IM40, EX10 и т.д.
        sa.Column('declaration_type', sa.String(20), nullable=False, server_default='IM40'),

        # Человекочитаемые правила (из инструкции)
        sa.Column('fill_instruction', sa.Text, nullable=False, server_default=''),
        sa.Column('fill_format', sa.Text, server_default=''),
        sa.Column('ai_rule', sa.Text, server_default=''),

        # Флаги поведения
        sa.Column('is_required', sa.Boolean, server_default='false'),
        sa.Column('skip', sa.Boolean, server_default='false'),
        sa.Column('requires_document', sa.Boolean, server_default='false'),

        # Значение по умолчанию и флаг
        sa.Column('default_value', sa.String(500), nullable=True),
        sa.Column('default_flag', sa.String(200), nullable=True),

        # Вычисляемое выражение (если значение считается автоматически)
        sa.Column('compute_expression', sa.Text, nullable=True),

        # Правила валидации: { type, min, max, values, pattern, ... }
        sa.Column('validation_rules', JSONB, server_default='{}'),

        # Приоритет источников документов: ["invoice", "contract", ...]
        # Заполняется сначала из YAML, потом уточняется пользователем
        sa.Column('source_priority', JSONB, server_default='[]'),

        # Маппинг полей источников: { "invoice": { "fields": ["seller_name", ...], "notes": "..." } }
        # Заполняется на втором шаге — когда пользователь уточняет из каких полей брать
        sa.Column('source_fields', JSONB, server_default='{}'),

        # Confidence по источнику: { "invoice": 0.8, "contract": 0.9 }
        sa.Column('confidence_map', JSONB, server_default='{}'),

        # Проверка конфликтов между источниками (человекочитаемое описание)
        sa.Column('conflict_check', sa.Text, nullable=True),

        # Целевое поле в core-api схеме (из YAML target.field)
        sa.Column('target_field', sa.String(200), nullable=True),
        sa.Column('target_kind', sa.String(50), nullable=True),

        # Мета
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('version', sa.String(20), server_default='3.0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('now()')),

        # Уникальность: одна запись на (граф + тип декларации)
        sa.UniqueConstraint('graph_number', 'declaration_type', name='uq_graph_decl_type'),

        schema='core',
    )

    op.create_index('ix_graph_rules_section', 'declaration_graph_rules', ['section'], schema='core')
    op.create_index('ix_graph_rules_decl_type', 'declaration_graph_rules', ['declaration_type'], schema='core')
    op.create_index('ix_graph_rules_number', 'declaration_graph_rules', ['graph_number'], schema='core')


def downgrade() -> None:
    op.drop_index('ix_graph_rules_number', table_name='declaration_graph_rules', schema='core')
    op.drop_index('ix_graph_rules_decl_type', table_name='declaration_graph_rules', schema='core')
    op.drop_index('ix_graph_rules_section', table_name='declaration_graph_rules', schema='core')
    op.drop_table('declaration_graph_rules', schema='core')
