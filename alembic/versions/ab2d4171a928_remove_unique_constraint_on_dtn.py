"""remove_unique_constraint_on_dtn

Revision ID: ab2d4171a928
Revises: 649b05e11ee8
Create Date: 2026-09-03 09:59:43.477605

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ab2d4171a928"
down_revision: Union[str, Sequence[str], None] = "649b05e11ee8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE main_db DROP INDEX ix_main_db_DB_DTN")
    op.execute("ALTER TABLE main_db ADD INDEX ix_main_db_DB_DTN (DB_DTN)")


def downgrade():
    op.execute("ALTER TABLE main_db DROP INDEX ix_main_db_DB_DTN")
    op.execute("ALTER TABLE main_db ADD UNIQUE INDEX ix_main_db_DB_DTN (DB_DTN)")
