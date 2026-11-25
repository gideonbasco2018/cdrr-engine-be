"""add softcopy_downloads table

Revision ID: 2caec359bbc4
Revises: 9f05fce5ab22
Create Date: 2026-11-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2caec359bbc4'
down_revision: Union[str, Sequence[str], None] = '9f05fce5ab22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('softcopy_downloads',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('file_type', sa.String(length=10), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('unit', sa.String(length=100), nullable=True),
    sa.Column('letter_count', sa.Integer(), nullable=False),
    sa.Column('dtns', sa.JSON(), nullable=False),
    sa.Column('downloaded_by', sa.String(length=150), nullable=True),
    sa.Column('downloaded_by_user_id', sa.Integer(), nullable=True),
    sa.Column('downloaded_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_softcopy_downloads_downloaded_by_user_id'), 'softcopy_downloads', ['downloaded_by_user_id'], unique=False)
    op.create_index(op.f('ix_softcopy_downloads_downloaded_at'), 'softcopy_downloads', ['downloaded_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_softcopy_downloads_downloaded_at'), table_name='softcopy_downloads')
    op.drop_index(op.f('ix_softcopy_downloads_downloaded_by_user_id'), table_name='softcopy_downloads')
    op.drop_table('softcopy_downloads')
