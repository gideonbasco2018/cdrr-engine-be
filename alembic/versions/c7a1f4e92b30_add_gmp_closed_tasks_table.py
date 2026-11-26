"""add gmp_closed_tasks table

Revision ID: c7a1f4e92b30
Revises: 2caec359bbc4
Create Date: 2026-11-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a1f4e92b30'
down_revision: Union[str, Sequence[str], None] = '2caec359bbc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('gmp_closed_tasks',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('gmp_record_id', sa.Integer(), nullable=False),
    sa.Column('dtn', sa.BigInteger(), nullable=True),
    sa.Column('reference_no', sa.String(length=50), nullable=True),
    sa.Column('closed_by_user_id', sa.Integer(), nullable=False),
    sa.Column('closed_by_user_name', sa.String(length=255), nullable=False),
    sa.Column('reason_for_closing', sa.String(length=255), nullable=False),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('date_released', sa.Date(), nullable=True),
    sa.Column('type_of_issuance_released', sa.String(length=255), nullable=True),
    sa.Column('open_logs_closed', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('closed_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['gmp_record_id'], ['gmp_record.GMP_ID'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gmp_closed_tasks_id'), 'gmp_closed_tasks', ['id'], unique=False)
    op.create_index(op.f('ix_gmp_closed_tasks_gmp_record_id'), 'gmp_closed_tasks', ['gmp_record_id'], unique=False)
    op.create_index(op.f('ix_gmp_closed_tasks_dtn'), 'gmp_closed_tasks', ['dtn'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Dropping the table drops its indexes and foreign key with it. (Dropping
    # the gmp_record_id index first fails on MySQL: the foreign key needs it.)
    op.drop_table('gmp_closed_tasks')
