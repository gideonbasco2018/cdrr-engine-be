"""merge donation module with clinical trial drugs table migration

Revision ID: 2d3f0eda9c45
Revises: 043cff92c450, df0cdce6c2f6
Create Date: 2026-09-24 03:21:50.347404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d3f0eda9c45'
down_revision: Union[str, Sequence[str], None] = ('043cff92c450', 'df0cdce6c2f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
