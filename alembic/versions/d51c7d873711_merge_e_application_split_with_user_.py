"""merge e_application split with user accomplished index placeholder

Revision ID: d51c7d873711
Revises: e1c5a9d3b7f2, 25a534063129
Create Date: 2026-10-01 09:24:29.389190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd51c7d873711'
down_revision: Union[str, Sequence[str], None] = ('e1c5a9d3b7f2', '25a534063129')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
