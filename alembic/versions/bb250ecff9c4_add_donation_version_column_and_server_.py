"""add donation version column and server-side defaults

Revision ID: bb250ecff9c4
Revises: 5965cf95f452
Create Date: 2026-09-16 01:03:13.719235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bb250ecff9c4'
down_revision: Union[str, Sequence[str], None] = '5965cf95f452'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('donations', sa.Column('version', sa.Integer(), server_default='1', nullable=False))
    # Give these three columns a database-level default too, so a raw
    # SQL insert that omits them no longer fails outright.
    op.alter_column('donations', 'application_uuid',
               existing_type=sa.String(length=36),
               server_default=sa.text('(UUID())'))
    op.alter_column('donations', 'status',
               existing_type=sa.String(length=30),
               server_default='For Evaluation')
    op.alter_column('donations', 'is_deleted',
               existing_type=sa.SmallInteger(),
               server_default='0')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('donations', 'is_deleted',
               existing_type=sa.SmallInteger(),
               server_default=None)
    op.alter_column('donations', 'status',
               existing_type=sa.String(length=30),
               server_default=None)
    op.alter_column('donations', 'application_uuid',
               existing_type=sa.String(length=36),
               server_default=None)
    op.drop_column('donations', 'version')
