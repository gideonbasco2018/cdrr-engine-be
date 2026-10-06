"""merge checklist bin into checklist_items (soft remove) + scan -> insert

- checklist_items.scanned_by / scanned_at renamed to inserted_by / inserted_at.
- Removing a DTN becomes a soft remove on checklist_items itself:
  is_removed + removed_by + removed_at (the last two NULL unless removed).
- Rows already in checklist_item_bin are copied in as removed rows, then
  the checklist_item_bin table is dropped.
- The "same DTN once per checklist" key now ignores removed rows, via a
  generated column active_dtn (= dtn while on the checklist, NULL once
  removed), so a removed DTN can be inserted again.

Revision ID: d2f6b8a4c913
Revises: c91e3a5d7f20
Create Date: 2026-10-05 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2f6b8a4c913'
down_revision: Union[str, Sequence[str], None] = 'c91e3a5d7f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # scan -> insert
    op.alter_column('checklist_items', 'scanned_by', new_column_name='inserted_by',
                    existing_type=sa.String(length=150), existing_nullable=True)
    op.alter_column('checklist_items', 'scanned_at', new_column_name='inserted_at',
                    existing_type=sa.DateTime(timezone=True), existing_nullable=True,
                    existing_server_default=sa.text('now()'))

    # soft remove fields
    op.add_column('checklist_items', sa.Column('is_removed', sa.SmallInteger(), server_default='0', nullable=False))
    op.add_column('checklist_items', sa.Column('removed_by', sa.String(length=150), nullable=True))
    op.add_column('checklist_items', sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_checklist_items_is_removed'), 'checklist_items', ['is_removed'], unique=False)

    # duplicate rule: only DTNs still on the checklist count
    op.execute(
        "ALTER TABLE checklist_items ADD COLUMN active_dtn VARCHAR(50) "
        "GENERATED ALWAYS AS (case when `is_removed` = 0 then `dtn` else NULL end) STORED"
    )
    op.drop_constraint('uq_checklist_items_checklist_dtn', 'checklist_items', type_='unique')
    op.create_unique_constraint('uq_checklist_items_checklist_active_dtn', 'checklist_items',
                                ['checklist_id', 'active_dtn'])

    # move the old bin in as removed rows, then drop it
    if sa.inspect(op.get_bind()).has_table('checklist_item_bin'):
        op.execute(
            "INSERT INTO checklist_items "
            "(checklist_id, dtn, inserted_by, inserted_at, is_removed, removed_by, removed_at) "
            "SELECT checklist_id, dtn, scanned_by, scanned_at, 1, removed_by, removed_at "
            "FROM checklist_item_bin ORDER BY id"
        )
        # drop_table takes its indexes with it (dropping the checklist_id index
        # alone fails — the foreign key needs it).
        op.drop_table('checklist_item_bin')


def downgrade() -> None:
    """Downgrade schema."""
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

    op.execute(
        "INSERT INTO checklist_item_bin "
        "(checklist_id, original_item_id, dtn, scanned_by, scanned_at, removed_by, removed_at) "
        "SELECT checklist_id, id, dtn, inserted_by, inserted_at, removed_by, removed_at "
        "FROM checklist_items WHERE is_removed = 1 ORDER BY id"
    )
    op.execute("DELETE FROM checklist_items WHERE is_removed = 1")

    op.drop_constraint('uq_checklist_items_checklist_active_dtn', 'checklist_items', type_='unique')
    op.create_unique_constraint('uq_checklist_items_checklist_dtn', 'checklist_items', ['checklist_id', 'dtn'])
    op.drop_column('checklist_items', 'active_dtn')

    op.drop_index(op.f('ix_checklist_items_is_removed'), table_name='checklist_items')
    op.drop_column('checklist_items', 'removed_at')
    op.drop_column('checklist_items', 'removed_by')
    op.drop_column('checklist_items', 'is_removed')

    op.alter_column('checklist_items', 'inserted_at', new_column_name='scanned_at',
                    existing_type=sa.DateTime(timezone=True), existing_nullable=True,
                    existing_server_default=sa.text('now()'))
    op.alter_column('checklist_items', 'inserted_by', new_column_name='scanned_by',
                    existing_type=sa.String(length=150), existing_nullable=True)
