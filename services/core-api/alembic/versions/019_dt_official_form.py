"""Align declaration models with official DT form (EEC KTS No 257)

New fields: Declaration (7 cols), DeclarationItem (5 cols), CustomsPayment (2 cols).
Type fixes: container_info String(200)->String(1), country_origin_code renamed to country_origin_name String(60).

Revision ID: 019
Revises: 018
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    decl_cols = {c['name'] for c in inspector.get_columns('declarations', schema='core')}
    item_cols = {c['name'] for c in inspector.get_columns('declaration_items', schema='core')}
    pay_cols = {c['name'] for c in inspector.get_columns('customs_payments', schema='core')}

    # -- Declaration: new fields --
    if 'special_ref_code' not in decl_cols:
        op.add_column('declarations', sa.Column('special_ref_code', sa.String(20), nullable=True), schema='core')
    if 'deal_specifics_code' not in decl_cols:
        op.add_column('declarations', sa.Column('deal_specifics_code', sa.String(2), nullable=True), schema='core')
    if 'payment_deferral' not in decl_cols:
        op.add_column('declarations', sa.Column('payment_deferral', sa.String(500), nullable=True), schema='core')
    if 'warehouse_requisites' not in decl_cols:
        op.add_column('declarations', sa.Column('warehouse_requisites', sa.String(500), nullable=True), schema='core')
    if 'transit_offices' not in decl_cols:
        op.add_column('declarations', sa.Column('transit_offices', sa.Text(), nullable=True), schema='core')
    if 'destination_office_code' not in decl_cols:
        op.add_column('declarations', sa.Column('destination_office_code', sa.String(100), nullable=True), schema='core')

    # -- Declaration: container_info String(200) -> String(1) (idempotent via UPDATE) --
    op.execute("UPDATE core.declarations SET container_info = '1' WHERE container_info IS NOT NULL AND container_info != '' AND container_info != '0'")
    op.execute("UPDATE core.declarations SET container_info = NULL WHERE container_info = ''")
    op.execute("ALTER TABLE core.declarations ALTER COLUMN container_info TYPE VARCHAR(1) USING container_info::varchar(1)")

    # -- Declaration: country_origin_code -> country_origin_name (idempotent) --
    if 'country_origin_code' in decl_cols and 'country_origin_name' not in decl_cols:
        op.alter_column('declarations', 'country_origin_code', new_column_name='country_origin_name', schema='core')
    if 'country_origin_name' in decl_cols or 'country_origin_code' not in decl_cols:
        op.execute("ALTER TABLE core.declarations ALTER COLUMN country_origin_name TYPE VARCHAR(60)")

    # -- DeclarationItem: new fields --
    if 'hs_code_letters' not in item_cols:
        op.add_column('declaration_items', sa.Column('hs_code_letters', sa.String(10), nullable=True), schema='core')
    if 'hs_code_extra' not in item_cols:
        op.add_column('declaration_items', sa.Column('hs_code_extra', sa.String(4), nullable=True), schema='core')
    if 'country_origin_pref_code' not in item_cols:
        op.add_column('declaration_items', sa.Column('country_origin_pref_code', sa.String(2), nullable=True), schema='core')
    if 'documents_json' not in item_cols:
        op.add_column('declaration_items', sa.Column('documents_json', JSONB(), nullable=True), schema='core')
    if 'statistical_value_usd' not in item_cols:
        op.add_column('declaration_items', sa.Column('statistical_value_usd', sa.DECIMAL(15, 2), nullable=True), schema='core')

    # -- CustomsPayment: new fields --
    if 'payment_type_code' not in pay_cols:
        op.add_column('customs_payments', sa.Column('payment_type_code', sa.String(4), nullable=True), schema='core')
    if 'payment_specifics' not in pay_cols:
        op.add_column('customs_payments', sa.Column('payment_specifics', sa.String(2), nullable=True), schema='core')


def downgrade() -> None:
    op.drop_column('customs_payments', 'payment_specifics', schema='core')
    op.drop_column('customs_payments', 'payment_type_code', schema='core')
    op.drop_column('declaration_items', 'statistical_value_usd', schema='core')
    op.drop_column('declaration_items', 'documents_json', schema='core')
    op.drop_column('declaration_items', 'country_origin_pref_code', schema='core')
    op.drop_column('declaration_items', 'hs_code_extra', schema='core')
    op.drop_column('declaration_items', 'hs_code_letters', schema='core')
    op.alter_column('declarations', 'country_origin_name', type_=sa.String(20), schema='core')
    op.alter_column('declarations', 'country_origin_name', new_column_name='country_origin_code', schema='core')
    op.alter_column('declarations', 'container_info', type_=sa.String(200), schema='core')
    op.drop_column('declarations', 'destination_office_code', schema='core')
    op.drop_column('declarations', 'transit_offices', schema='core')
    op.drop_column('declarations', 'warehouse_requisites', schema='core')
    op.drop_column('declarations', 'payment_deferral', schema='core')
    op.drop_column('declarations', 'deal_specifics_code', schema='core')
    op.drop_column('declarations', 'special_ref_code', schema='core')
