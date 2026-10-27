"""add e_app_fgmp_worksheet table

Revision ID: 9f05fce5ab22
Revises: 888373cf81bb
Create Date: 2026-10-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f05fce5ab22'
down_revision: Union[str, Sequence[str], None] = '888373cf81bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('e_app_fgmp_worksheet',
    sa.Column('worksheet_uuid', sa.String(length=36), nullable=False),
    sa.Column('application_uuid', sa.String(length=36), nullable=False),
    sa.Column('history_uuid', sa.String(length=36), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('variant', sa.String(length=1), nullable=False),
    sa.Column('gmp_evidence', sa.JSON(), nullable=True),
    sa.Column('issuing_authority', sa.String(length=255), nullable=True),
    sa.Column('issuing_country', sa.String(length=100), nullable=True),
    sa.Column('foreign_certificate_number', sa.String(length=100), nullable=True),
    sa.Column('foreign_certificate_validity', sa.String(length=100), nullable=True),
    sa.Column('inspection_dates', sa.String(length=100), nullable=True),
    sa.Column('date_issued_text', sa.Text(), nullable=True),
    sa.Column('approved_dosage_forms_note', sa.Text(), nullable=True),
    sa.Column('applied_forms', sa.JSON(), nullable=True),
    sa.Column('approved_products', sa.JSON(), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('compliance_notes', sa.Text(), nullable=True),
    sa.Column('recommendation', sa.String(length=20), nullable=True),
    sa.Column('annex_c', sa.JSON(), nullable=True),
    sa.Column('annex_rows', sa.JSON(), nullable=True),
    sa.Column('saved_by_user_uuid', sa.String(length=36), nullable=False),
    sa.Column('saved_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_by', sa.String(length=36), nullable=True),
    sa.ForeignKeyConstraint(['application_uuid'], ['e_application.application_uuid'], ),
    sa.ForeignKeyConstraint(['history_uuid'], ['e_app_history.history_uuid'], ),
    sa.ForeignKeyConstraint(['saved_by_user_uuid'], ['users.user_uuid'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.user_uuid'], ),
    sa.PrimaryKeyConstraint('worksheet_uuid'),
    sa.UniqueConstraint('application_uuid', 'version', name='uq_e_app_fgmp_worksheet_version')
    )
    op.create_index(op.f('ix_e_app_fgmp_worksheet_worksheet_uuid'), 'e_app_fgmp_worksheet', ['worksheet_uuid'], unique=False)
    op.create_index(op.f('ix_e_app_fgmp_worksheet_application_uuid'), 'e_app_fgmp_worksheet', ['application_uuid'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_e_app_fgmp_worksheet_application_uuid'), table_name='e_app_fgmp_worksheet')
    op.drop_index(op.f('ix_e_app_fgmp_worksheet_worksheet_uuid'), table_name='e_app_fgmp_worksheet')
    op.drop_table('e_app_fgmp_worksheet')
