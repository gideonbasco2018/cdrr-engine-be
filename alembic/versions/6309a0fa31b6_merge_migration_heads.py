"""merge migration heads

Revision ID: 6309a0fa31b6
Revises: c64180b7184d, e675fa62c950
Create Date: 2026-07-15 00:52:49.572495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6309a0fa31b6'
down_revision: Union[str, Sequence[str], None] = ('c64180b7184d', 'e675fa62c950')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
