"""merge donation module with clinical trials migrations

Revision ID: 8b86868680c0
Revises: bb250ecff9c4, 2a77c1a7a02e
Create Date: 2026-09-16 08:07:21.968245

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b86868680c0'
down_revision: Union[str, Sequence[str], None] = ('bb250ecff9c4', '2a77c1a7a02e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
