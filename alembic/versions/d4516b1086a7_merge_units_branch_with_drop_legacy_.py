"""merge units branch with drop legacy lead columns

Revision ID: d4516b1086a7
Revises: 9b2605866dc0, c34a976cd932
Create Date: 2026-08-24 05:12:21.716595

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4516b1086a7'
down_revision: Union[str, Sequence[str], None] = ('9b2605866dc0', 'c34a976cd932')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
