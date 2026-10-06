"""add checklist label

Free-text tag for a batch (e.g. "URGENT", "CPR"), printed big on the PDF.

Revision ID: c91e3a5d7f20
Revises: b4d8f1c27e95
Create Date: 2026-10-05 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c91e3a5d7f20'
down_revision: Union[str, Sequence[str], None] = 'b4d8f1c27e95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('checklists', sa.Column('label', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('checklists', 'label')
