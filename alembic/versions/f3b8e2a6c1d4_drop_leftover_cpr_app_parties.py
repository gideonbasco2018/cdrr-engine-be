"""drop leftover cpr_app_parties table

The cpr_* -> e_app_* rename (878560da0186) created a new e_app_parties table
instead of renaming cpr_app_parties, so the old table was left behind and
nothing uses it anymore. Any rows still in it are copied into e_app_parties
first (skipping ones already there), then the old table is dropped.

Revision ID: f3b8e2a6c1d4
Revises: d51c7d873711
Create Date: 2026-10-02 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3b8e2a6c1d4'
down_revision: Union[str, Sequence[str], None] = 'd51c7d873711'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = "party_uuid, application_uuid, party_type, name, address, tin, lto_no, country"


def upgrade() -> None:
    """Upgrade schema."""
    if not sa.inspect(op.get_bind()).has_table("cpr_app_parties"):
        return

    # Keep any data that never made it into e_app_parties
    op.execute(
        f"INSERT INTO e_app_parties ({COLUMNS}) "
        f"SELECT {COLUMNS} FROM cpr_app_parties c "
        f"WHERE NOT EXISTS (SELECT 1 FROM e_app_parties e WHERE e.party_uuid = c.party_uuid)"
    )
    op.drop_table("cpr_app_parties")


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate the empty table with its old structure (data stays in e_app_parties)
    op.create_table('cpr_app_parties',
    sa.Column('party_uuid', sa.String(length=36), nullable=False),
    sa.Column('application_uuid', sa.String(length=36), nullable=False),
    sa.Column('party_type', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('tin', sa.String(length=50), nullable=True),
    sa.Column('lto_no', sa.String(length=100), nullable=True),
    sa.Column('country', sa.String(length=100), nullable=True),
    sa.ForeignKeyConstraint(['application_uuid'], ['e_application.application_uuid'], ),
    sa.PrimaryKeyConstraint('party_uuid')
    )
    op.create_index(op.f('ix_cpr_app_parties_party_uuid'), 'cpr_app_parties', ['party_uuid'], unique=False)
