"""split e_application into mother + e_application_mivn / e_application_fgmp

e_application keeps only the columns every application type shares (+ tin).
The MiV-N-only columns move to e_application_mivn (existing rows are copied
over first), and FGMP gets its own e_application_fgmp. Both child tables are
1:1 with e_application. Also seeds the MVN and FGMP e_process rows.

Revision ID: e1c5a9d3b7f2
Revises: b73817a0bd86
Create Date: 2026-10-01 14:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1c5a9d3b7f2'
down_revision: Union[str, Sequence[str], None] = 'b73817a0bd86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# MiV-N-only columns that move from e_application to e_application_mivn
MIVN_COLUMNS = [
    ("validity", sa.String(length=100)),
    ("brand_name", sa.String(length=255)),
    ("generic_name", sa.String(length=255)),
    ("dosage_strength", sa.String(length=255)),
    ("dosage_form_route", sa.String(length=255)),
    ("classification", sa.String(length=255)),
    ("product_category", sa.String(length=255)),
    ("essential_drug_list", sa.String(length=255)),
    ("pharmacologic_category", sa.String(length=255)),
    ("shelf_life", sa.String(length=255)),
    ("storage_condition", sa.String(length=255)),
    ("packaging", sa.String(length=255)),
    ("suggested_retail_price", sa.String(length=100)),
    ("registration_number", sa.String(length=100)),
    ("mother_application_type", sa.String(length=100)),
    ("old_rsn_other_dtn", sa.String(length=255)),
]

PROCESSES = [
    ("MVN", "Minor Variation Notification"),
    ("FGMP", "Foreign Good Manufacturing Practice"),
]


def upgrade() -> None:
    """Upgrade schema."""
    # 1. MiV-N child table
    op.create_table('e_application_mivn',
    sa.Column('mivn_uuid', sa.String(length=36), nullable=False),
    sa.Column('application_uuid', sa.String(length=36), nullable=False),
    *[sa.Column(name, col_type, nullable=True) for name, col_type in MIVN_COLUMNS],
    sa.ForeignKeyConstraint(['application_uuid'], ['e_application.application_uuid'], ),
    sa.PrimaryKeyConstraint('mivn_uuid')
    )
    op.create_index(op.f('ix_e_application_mivn_mivn_uuid'), 'e_application_mivn', ['mivn_uuid'], unique=False)

    # 2. FGMP child table
    op.create_table('e_application_fgmp',
    sa.Column('fgmp_uuid', sa.String(length=36), nullable=False),
    sa.Column('application_uuid', sa.String(length=36), nullable=False),
    sa.Column('dtn', sa.String(length=50), nullable=True),
    sa.Column('related_dtn', sa.String(length=50), nullable=True),
    sa.Column('date_received', sa.Date(), nullable=True),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('foreign_manufacturer', sa.String(length=255), nullable=True),
    sa.Column('foreign_manufacturer_address', sa.String(length=500), nullable=True),
    sa.Column('foreign_manufacturer_country', sa.String(length=100), nullable=True),
    sa.Column('product_line', sa.String(length=500), nullable=True),
    sa.Column('previous_certificate_number', sa.String(length=100), nullable=True),
    sa.Column('previous_certificate_validity', sa.String(length=100), nullable=True),
    sa.Column('type_of_issuance', sa.String(length=255), nullable=True),
    sa.Column('certificate_number', sa.String(length=100), nullable=True),
    sa.ForeignKeyConstraint(['application_uuid'], ['e_application.application_uuid'], ),
    sa.PrimaryKeyConstraint('fgmp_uuid')
    )
    op.create_index(op.f('ix_e_application_fgmp_fgmp_uuid'), 'e_application_fgmp', ['fgmp_uuid'], unique=False)
    op.create_index(op.f('ix_e_application_fgmp_dtn'), 'e_application_fgmp', ['dtn'], unique=False)

    # 3. Copy existing MiV-N data into the child table, then drop it from the mother
    cols = ", ".join(name for name, _ in MIVN_COLUMNS)
    op.execute(
        f"INSERT INTO e_application_mivn (mivn_uuid, application_uuid, {cols}) "
        f"SELECT UUID(), application_uuid, {cols} FROM e_application"
    )
    for name, _ in MIVN_COLUMNS:
        op.drop_column('e_application', name)

    # 4. Seed the process rows the create endpoints look up
    for code, title in PROCESSES:
        op.execute(
            sa.text(
                "INSERT INTO e_process (process_uuid, process_code, process_title, is_active) "
                "SELECT :uuid, :code, :title, 1 FROM DUAL "
                "WHERE NOT EXISTS (SELECT 1 FROM e_process WHERE process_code = :code)"
            ).bindparams(uuid=str(uuid.uuid4()), code=code, title=title)
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Put the MiV-N columns back on the mother table and copy the data back
    for name, col_type in MIVN_COLUMNS:
        op.add_column('e_application', sa.Column(name, col_type, nullable=True))
    sets = ", ".join(f"a.{name} = m.{name}" for name, _ in MIVN_COLUMNS)
    op.execute(
        f"UPDATE e_application a JOIN e_application_mivn m "
        f"ON m.application_uuid = a.application_uuid SET {sets}"
    )

    op.drop_index(op.f('ix_e_application_fgmp_dtn'), table_name='e_application_fgmp')
    op.drop_index(op.f('ix_e_application_fgmp_fgmp_uuid'), table_name='e_application_fgmp')
    op.drop_table('e_application_fgmp')
    op.drop_index(op.f('ix_e_application_mivn_mivn_uuid'), table_name='e_application_mivn')
    op.drop_table('e_application_mivn')
    # e_process rows are left in place: other data may already point to them
