"""checklist soft delete and item bin

Deleting a checklist becomes a soft delete (is_deleted/deleted_at/deleted_by
on checklists). Removing a DTN moves it into the new checklist_item_bin
table, which has no restore.

Revision ID: b4d8f1c27e95
Revises: a7c2e9d41b03
Create Date: 2026-10-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4d8f1c27e95'
down_revision: Union[str, Sequence[str], None] = 'a7c2e9d41b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('checklists', sa.Column('is_deleted', sa.SmallInteger(), server_default='0', nullable=False))
    op.add_column('checklists', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('checklists', sa.Column('deleted_by', sa.String(length=150), nullable=True))
    op.create_index(op.f('ix_checklists_is_deleted'), 'checklists', ['is_deleted'], unique=False)

    op.create_table(
        'checklist_item_bin',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('checklist_id', sa.Integer(), nullable=False),
        sa.Column('original_item_id', sa.Integer(), nullable=False),
        sa.Column('dtn', sa.String(length=50), nullable=False),
        sa.Column('scanned_by', sa.String(length=150), nullable=True),
        sa.Column('scanned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('removed_by', sa.String(length=150), nullable=True),
        sa.Column('removed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['checklist_id'], ['checklists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_checklist_item_bin_checklist_id'), 'checklist_item_bin', ['checklist_id'], unique=False)
    op.create_index(op.f('ix_checklist_item_bin_dtn'), 'checklist_item_bin', ['dtn'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_checklist_item_bin_dtn'), table_name='checklist_item_bin')
    op.drop_index(op.f('ix_checklist_item_bin_checklist_id'), table_name='checklist_item_bin')
    op.drop_table('checklist_item_bin')
    op.drop_index(op.f('ix_checklists_is_deleted'), table_name='checklists')
    op.drop_column('checklists', 'deleted_by')
    op.drop_column('checklists', 'deleted_at')
    op.drop_column('checklists', 'is_deleted')
