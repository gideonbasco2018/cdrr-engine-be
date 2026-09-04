"""merge gmp product line widen with application logs task tracking

Revision ID: 77851f7245e3
Revises: ab38bce71de5, b45a50220706
Create Date: 2026-09-04 08:39:16.314919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77851f7245e3'
down_revision: Union[str, Sequence[str], None] = ('ab38bce71de5', 'b45a50220706')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
