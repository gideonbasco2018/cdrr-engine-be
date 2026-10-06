"""add checklist item subject (copied from FIS)

checklist_items.subject — the DTN's subject from FIS
(document_tracker.docreceivingtbl), kept as it was at insert time.
checklist_items.subject_status — pending / found / not_found / error.
Existing rows start as 'pending' so "Refresh subjects" can fill them in.

Revision ID: e5a7c3f9b218
Revises: d2f6b8a4c913
Create Date: 2026-10-06 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a7c3f9b218'
down_revision: Union[str, Sequence[str], None] = 'd2f6b8a4c913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('checklist_items', sa.Column('subject', sa.Text(), nullable=True))
    op.add_column('checklist_items', sa.Column('subject_status', sa.String(length=20),
                                               server_default='pending', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('checklist_items', 'subject_status')
    op.drop_column('checklist_items', 'subject')
