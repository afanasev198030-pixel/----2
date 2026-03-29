"""Refactor declaration status model: 3 independent axes (status, processing_status, signature_status)

Old statuses: draft, checking_lvl1, checking_lvl2, final_check, signed, sent,
              registered, docs_requested, inspection, released, rejected
New statuses: new, requires_attention, ready_to_send, sent

Old processing_status: NULL, "complete", "failed"
New processing_status: not_started, processing, auto_filled, processing_error

New field signature_status: unsigned, signed

Revision ID: 029
Revises: 028
Create Date: 2026-03-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '029'
down_revision: Union[str, None] = '028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS_MIGRATION = {
    "draft": ("new", "unsigned"),
    "checking_lvl1": ("requires_attention", "unsigned"),
    "checking_lvl2": ("requires_attention", "unsigned"),
    "final_check": ("requires_attention", "unsigned"),
    "signed": ("ready_to_send", "signed"),
    "sent": ("sent", "signed"),
    "registered": ("sent", "signed"),
    "docs_requested": ("sent", "signed"),
    "inspection": ("sent", "signed"),
    "released": ("sent", "signed"),
    "rejected": ("sent", "signed"),
}

PROCESSING_MIGRATION = {
    "complete": "auto_filled",
    "failed": "processing_error",
}


def upgrade() -> None:
    conn = op.get_bind()

    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = 'core' AND table_name = 'declarations' "
        "AND column_name = 'signature_status'"
    ))
    if result.fetchone() is None:
        op.add_column(
            'declarations',
            sa.Column('signature_status', sa.String(length=20), nullable=False, server_default='unsigned'),
            schema='core',
        )

    op.alter_column(
        'declarations', 'status',
        type_=sa.String(length=30),
        schema='core',
    )

    for old_status, (new_status, sig) in STATUS_MIGRATION.items():
        conn.execute(sa.text(
            "UPDATE core.declarations "
            "SET status = :new_status, signature_status = :sig "
            "WHERE status = :old_status"
        ), {"new_status": new_status, "sig": sig, "old_status": old_status})

    conn.execute(sa.text(
        "UPDATE core.declarations "
        "SET processing_status = 'not_started' "
        "WHERE processing_status IS NULL"
    ))
    for old_proc, new_proc in PROCESSING_MIGRATION.items():
        conn.execute(sa.text(
            "UPDATE core.declarations "
            "SET processing_status = :new_proc "
            "WHERE processing_status = :old_proc"
        ), {"new_proc": new_proc, "old_proc": old_proc})

    op.alter_column(
        'declarations', 'processing_status',
        type_=sa.String(length=30),
        nullable=False,
        server_default='not_started',
        schema='core',
    )


def downgrade() -> None:
    conn = op.get_bind()

    reverse_status = {
        "new": "draft",
        "requires_attention": "draft",
        "ready_to_send": "draft",
        "sent": "sent",
    }
    for new_status, old_status in reverse_status.items():
        conn.execute(sa.text(
            "UPDATE core.declarations SET status = :old WHERE status = :new"
        ), {"old": old_status, "new": new_status})

    conn.execute(sa.text(
        "UPDATE core.declarations SET processing_status = NULL "
        "WHERE processing_status = 'not_started'"
    ))
    conn.execute(sa.text(
        "UPDATE core.declarations SET processing_status = 'complete' "
        "WHERE processing_status = 'auto_filled'"
    ))
    conn.execute(sa.text(
        "UPDATE core.declarations SET processing_status = 'failed' "
        "WHERE processing_status = 'processing_error'"
    ))

    op.alter_column(
        'declarations', 'processing_status',
        type_=sa.String(length=20),
        nullable=True,
        server_default=None,
        schema='core',
    )
    op.alter_column(
        'declarations', 'status',
        type_=sa.String(length=20),
        schema='core',
    )
    op.drop_column('declarations', 'signature_status', schema='core')
