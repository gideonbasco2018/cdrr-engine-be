"""add checklists and checklist_items tables

Backs the Checklist page: one checklist per batch of forwarded DTNs, one
checklist_items row per scanned DTN (scan time set by the server).

Revision ID: a7c2e9d41b03
Revises: f3b8e2a6c1d4
Create Date: 2026-10-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c2e9d41b03'
down_revision: Union[str, Sequence[str], None] = 'f3b8e2a6c1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'checklists',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_by', sa.String(length=150), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_checklists_id'), 'checklists', ['id'], unique=False)

    op.create_table(
        'checklist_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('checklist_id', sa.Integer(), nullable=False),
        sa.Column('dtn', sa.String(length=50), nullable=False),
        sa.Column('scanned_by', sa.String(length=150), nullable=True),
        sa.Column('scanned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['checklist_id'], ['checklists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('checklist_id', 'dtn', name='uq_checklist_items_checklist_dtn'),
    )
    op.create_index(op.f('ix_checklist_items_checklist_id'), 'checklist_items', ['checklist_id'], unique=False)
    op.create_index(op.f('ix_checklist_items_dtn'), 'checklist_items', ['dtn'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_checklist_items_dtn'), table_name='checklist_items')
    op.drop_index(op.f('ix_checklist_items_checklist_id'), table_name='checklist_items')
    op.drop_table('checklist_items')
    op.drop_index(op.f('ix_checklists_id'), table_name='checklists')
    op.drop_table('checklists')
