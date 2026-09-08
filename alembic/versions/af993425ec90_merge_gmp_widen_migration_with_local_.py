"""merge gmp widen migration with local changes

Revision ID: af993425ec90
Revises: 77851f7245e3, d2d94da241e0
Create Date: 2026-09-08 17:15:15.606660

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af993425ec90'
down_revision: Union[str, Sequence[str], None] = ('77851f7245e3', 'd2d94da241e0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
