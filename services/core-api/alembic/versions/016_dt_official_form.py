"""Align declaration models with official DT form (EEC KTS No 257)

New fields: Declaration (7 cols), DeclarationItem (5 cols), CustomsPayment (2 cols).
Type fixes: container_info String(200)->String(1), country_origin_code renamed to country_origin_name String(60).

Revision ID: 016
Revises: 015
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Declaration: new fields --
    op.add_column('declarations', sa.Column('special_ref_code', sa.String(20), nullable=True), schema='core')
    op.add_column('declarations', sa.Column('deal_specifics_code', sa.String(2), nullable=True), schema='core')
    op.add_column('declarations', sa.Column('payment_deferral', sa.String(500), nullable=True), schema='core')
    op.add_column('declarations', sa.Column('warehouse_requisites', sa.String(500), nullable=True), schema='core')
    op.add_column('declarations', sa.Column('transit_offices', sa.Text(), nullable=True), schema='core')
    op.add_column('declarations', sa.Column('destination_office_code', sa.String(100), nullable=True), schema='core')

    # -- Declaration: container_info String(200) -> String(1) --
    op.execute("UPDATE core.declarations SET container_info = '1' WHERE container_info IS NOT NULL AND container_info != '' AND container_info != '0'")
    op.execute("UPDATE core.declarations SET container_info = NULL WHERE container_info = ''")
    op.alter_column('declarations', 'container_info', type_=sa.String(1), schema='core')

    # -- Declaration: country_origin_code -> country_origin_name, String(20) -> String(60) --
    op.alter_column('declarations', 'country_origin_code', new_column_name='country_origin_name', schema='core')
    op.alter_column('declarations', 'country_origin_name', type_=sa.String(60), schema='core')

    # -- DeclarationItem: new fields --
    op.add_column('declaration_items', sa.Column('hs_code_letters', sa.String(10), nullable=True), schema='core')
    op.add_column('declaration_items', sa.Column('hs_code_extra', sa.String(4), nullable=True), schema='core')
    op.add_column('declaration_items', sa.Column('country_origin_pref_code', sa.String(2), nullable=True), schema='core')
    op.add_column('declaration_items', sa.Column('documents_json', JSONB(), nullable=True), schema='core')
    op.add_column('declaration_items', sa.Column('statistical_value_usd', sa.DECIMAL(15, 2), nullable=True), schema='core')

    # -- CustomsPayment: new fields --
    op.add_column('customs_payments', sa.Column('payment_type_code', sa.String(4), nullable=True), schema='core')
    op.add_column('customs_payments', sa.Column('payment_specifics', sa.String(2), nullable=True), schema='core')


def downgrade() -> None:
    # -- CustomsPayment: drop new fields --
    op.drop_column('customs_payments', 'payment_specifics', schema='core')
    op.drop_column('customs_payments', 'payment_type_code', schema='core')

    # -- DeclarationItem: drop new fields --
    op.drop_column('declaration_items', 'statistical_value_usd', schema='core')
    op.drop_column('declaration_items', 'documents_json', schema='core')
    op.drop_column('declaration_items', 'country_origin_pref_code', schema='core')
    op.drop_column('declaration_items', 'hs_code_extra', schema='core')
    op.drop_column('declaration_items', 'hs_code_letters', schema='core')

    # -- Declaration: revert country_origin_name -> country_origin_code --
    op.alter_column('declarations', 'country_origin_name', type_=sa.String(20), schema='core')
    op.alter_column('declarations', 'country_origin_name', new_column_name='country_origin_code', schema='core')

    # -- Declaration: revert container_info String(1) -> String(200) --
    op.alter_column('declarations', 'container_info', type_=sa.String(200), schema='core')

    # -- Declaration: drop new fields --
    op.drop_column('declarations', 'destination_office_code', schema='core')
    op.drop_column('declarations', 'transit_offices', schema='core')
    op.drop_column('declarations', 'warehouse_requisites', schema='core')
    op.drop_column('declarations', 'payment_deferral', schema='core')
    op.drop_column('declarations', 'deal_specifics_code', schema='core')
    op.drop_column('declarations', 'special_ref_code', schema='core')
