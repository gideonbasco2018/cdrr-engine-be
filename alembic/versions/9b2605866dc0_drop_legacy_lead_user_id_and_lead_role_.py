"""drop legacy lead_user_id and lead_role, enforce unit_id group_id not null

Revision ID: 9b2605866dc0
Revises: 38c54a680adf
Create Date: 2026-08-18 14:45:11.702937

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b2605866dc0'
down_revision: Union[str, Sequence[str], None] = '38c54a680adf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
