"""Change DB_DATE_ISSUED from Date to Text

Revision ID: 5fbd4784f543
Revises: bfb06e954a8b
Create Date: 2026-01-09 16:46:16.108051

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = '5fbd4784f543'
down_revision: Union[str, Sequence[str], None] = 'bfb06e954a8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - only change DB_DATE_ISSUED column."""
    op.alter_column('main_db', 'DB_DATE_ISSUED',
               existing_type=mysql.DATE(),
               type_=sa.Text(),
               existing_comment='Date Issued',
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema - revert DB_DATE_ISSUED back to DATE."""
    op.alter_column('main_db', 'DB_DATE_ISSUED',
               existing_type=sa.Text(),
               type_=mysql.DATE(),
               existing_comment='Date Issued',
               existing_nullable=True)