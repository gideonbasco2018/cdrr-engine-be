"""merge units table with gmp reference no branch

Revision ID: c34a976cd932
Revises: 38c54a680adf, 60c3776a439d
Create Date: 2026-08-24 01:48:40.872709

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c34a976cd932'
down_revision: Union[str, Sequence[str], None] = ('38c54a680adf', '60c3776a439d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
