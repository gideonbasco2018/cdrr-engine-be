"""merge donation widen migration with cpr table of changes

Revision ID: 043cff92c450
Revises: 845bad808b29, 2da1d9919873
Create Date: 2026-09-23 00:21:15.978607

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '043cff92c450'
down_revision: Union[str, Sequence[str], None] = ('845bad808b29', '2da1d9919873')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
