"""merge divergent heads

Revision ID: 60c3776a439d
Revises: 54131bf97b17, adb7dfef3492
Create Date: 2026-08-03 06:22:05.549715

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '60c3776a439d'
down_revision: Union[str, Sequence[str], None] = ('54131bf97b17', 'adb7dfef3492')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass