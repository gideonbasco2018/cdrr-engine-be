"""Additional Column in main_db (db app remarks)

Revision ID: b05fc78a9de2
Revises: ed90153df997
Create Date: 2026-01-13 14:26:54.529185
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'b05fc78a9de2'
down_revision: Union[str, Sequence[str], None] = 'ed90153df997'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # -----------------------------
    # Add user_name column if missing
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('application_logs')]
    if 'user_name' not in columns:
        op.add_column('application_logs', sa.Column('user_name', sa.String(length=255), nullable=True))

    # -----------------------------
    # Alter existing columns (remove comments)
    op.alter_column('application_logs', 'application_step',
               existing_type=mysql.VARCHAR(length=255),
               comment=None,
               existing_comment='Current Application Step',
               existing_nullable=True)
    op.alter_column('application_logs', 'application_status',
               existing_type=mysql.VARCHAR(length=255),
               comment=None,
               existing_comment='Application Status',
               existing_nullable=True)
    op.alter_column('application_logs', 'application_decision',
               existing_type=mysql.VARCHAR(length=255),
               comment=None,
               existing_comment='Application Decision',
               existing_nullable=True)
    op.alter_column('application_logs', 'application_remarks',
               existing_type=mysql.TEXT(),
               comment=None,
               existing_comment='Application Remarks',
               existing_nullable=True)
    op.alter_column('application_logs', 'start_date',
               existing_type=mysql.DATETIME(),
               comment=None,
               existing_comment='Start Date',
               existing_nullable=True)
    op.alter_column('application_logs', 'accomplished_date',
               existing_type=mysql.DATETIME(),
               comment=None,
               existing_comment='Accomplished Date',
               existing_nullable=True)

    # -----------------------------
    # Keep main_db_dtn as BIGINT (foreign key safe)
    op.alter_column('application_logs', 'main_db_dtn',
               existing_type=mysql.BIGINT(),
               comment=None,
               existing_comment='Foreign Key - DTN from MainDB',
               existing_nullable=False)

    # -----------------------------
    # Alter timestamps
    op.alter_column('application_logs', 'created_at',
               existing_type=mysql.DATETIME(),
               comment=None,
               existing_comment='Record Created At',
               existing_nullable=True,
               existing_server_default=sa.text('(now())'))
    op.alter_column('application_logs', 'updated_at',
               existing_type=mysql.DATETIME(),
               comment=None,
               existing_comment='Record Updated At',
               existing_nullable=True,
               existing_server_default=sa.text('(now())'))

    # -----------------------------
    # Create indexes
    op.create_index(op.f('ix_application_logs_id'), 'application_logs', ['id'], unique=False)
    op.create_index(op.f('ix_application_logs_main_db_dtn'), 'application_logs', ['main_db_dtn'], unique=False)

    # -----------------------------
    # Drop old user_id foreign key and column if it exists
    fk_constraints = [fk['name'] for fk in inspector.get_foreign_keys('application_logs')]
    if 'application_logs_ibfk_2' in fk_constraints:
        op.drop_constraint('application_logs_ibfk_2', 'application_logs', type_='foreignkey')

    if 'user_id' in columns:
        op.drop_column('application_logs', 'user_id')

    # -----------------------------
    # Add column to main_db
    columns_main_db = [col['name'] for col in inspector.get_columns('main_db')]
    if 'DB_APP_REMARKS' not in columns_main_db:
        op.add_column('main_db', sa.Column('DB_APP_REMARKS', sa.Text(), nullable=True, comment='Application Remarks'))


def downgrade() -> None:
    """Downgrade schema."""

    conn = op.get_bind()
    inspector = inspect(conn)

    # Remove DB_APP_REMARKS from main_db if exists
    columns_main_db = [col['name'] for col in inspector.get_columns('main_db')]
    if 'DB_APP_REMARKS' in columns_main_db:
        op.drop_column('main_db', 'DB_APP_REMARKS')

    # Add back user_id column and foreign key if missing
    columns_logs = [col['name'] for col in inspector.get_columns('application_logs')]
    fk_constraints = [fk['name'] for fk in inspector.get_foreign_keys('application_logs')]

    if 'user_id' not in columns_logs:
        op.add_column('application_logs', sa.Column('user_id', mysql.INTEGER(), autoincrement=False, nullable=True, comment='User ID Processing the Application'))

    if 'application_logs_ibfk_2' not in fk_constraints:
        op.create_foreign_key('application_logs_ibfk_2', 'application_logs', 'users', ['user_id'], ['id'], onupdate='CASCADE', ondelete='SET NULL')

    # Drop indexes
    op.drop_index(op.f('ix_application_logs_main_db_dtn'), table_name='application_logs')
    op.drop_index(op.f('ix_application_logs_id'), table_name='application_logs')

    # Revert column comment removals (types remain)
    op.alter_column('application_logs', 'updated_at',
               existing_type=mysql.DATETIME(),
               comment='Record Updated At',
               existing_nullable=True,
               existing_server_default=sa.text('(now())'))
    op.alter_column('application_logs', 'created_at',
               existing_type=mysql.DATETIME(),
               comment='Record Created At',
               existing_nullable=True,
               existing_server_default=sa.text('(now())'))
    op.alter_column('application_logs', 'main_db_dtn',
               existing_type=mysql.BIGINT(),
               comment='Foreign Key - DTN from MainDB',
               existing_nullable=False)
    op.alter_column('application_logs', 'accomplished_date',
               existing_type=mysql.DATETIME(),
               comment='Accomplished Date',
               existing_nullable=True)
    op.alter_column('application_logs', 'start_date',
               existing_type=mysql.DATETIME(),
               comment='Start Date',
               existing_nullable=True)
    op.alter_column('application_logs', 'application_remarks',
               existing_type=mysql.TEXT(),
               comment='Application Remarks',
               existing_nullable=True)
    op.alter_column('application_logs', 'application_decision',
               existing_type=mysql.VARCHAR(length=255),
               comment='Application Decision',
               existing_nullable=True)
    op.alter_column('application_logs', 'application_status',
               existing_type=mysql.VARCHAR(length=255),
               comment='Application Status',
               existing_nullable=True)
    op.alter_column('application_logs', 'application_step',
               existing_type=mysql.VARCHAR(length=255),
               comment='Current Application Step',
               existing_nullable=True)

    # Remove user_name if exists
    if 'user_name' in columns_logs:
        op.drop_column('application_logs', 'user_name')
