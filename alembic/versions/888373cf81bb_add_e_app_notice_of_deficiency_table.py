"""add e_app_notice_of_deficiency table

Revision ID: 888373cf81bb
Revises: aef3f5e49a2a
Create Date: 2026-10-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '888373cf81bb'
down_revision: Union[str, Sequence[str], None] = 'aef3f5e49a2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('e_app_notice_of_deficiency',
    sa.Column('nod_uuid', sa.String(length=36), nullable=False),
    sa.Column('application_uuid', sa.String(length=36), nullable=False),
    sa.Column('history_uuid', sa.String(length=36), nullable=True),
    sa.Column('activity', sa.String(length=255), nullable=False),
    sa.Column('nod_number', sa.Integer(), nullable=False),
    sa.Column('deficiencies', sa.Text(), nullable=False),
    sa.Column('requested_documents', sa.JSON(), nullable=True),
    sa.Column('issued_date', sa.Date(), nullable=False),
    sa.Column('working_days', sa.Integer(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('extended_due_date', sa.Date(), nullable=True),
    sa.Column('extension_reason', sa.Text(), nullable=True),
    sa.Column('extended_by_user_uuid', sa.String(length=36), nullable=True),
    sa.Column('extended_at', sa.DateTime(), nullable=True),
    sa.Column('documents_received_date', sa.Date(), nullable=True),
    sa.Column('received_by_user_uuid', sa.String(length=36), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('issued_by_user_uuid', sa.String(length=36), nullable=False),
    sa.Column('email_sent_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_by', sa.String(length=36), nullable=True),
    sa.ForeignKeyConstraint(['application_uuid'], ['e_application.application_uuid'], ),
    sa.ForeignKeyConstraint(['history_uuid'], ['e_app_history.history_uuid'], ),
    sa.ForeignKeyConstraint(['extended_by_user_uuid'], ['users.user_uuid'], ),
    sa.ForeignKeyConstraint(['received_by_user_uuid'], ['users.user_uuid'], ),
    sa.ForeignKeyConstraint(['issued_by_user_uuid'], ['users.user_uuid'], ),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.user_uuid'], ),
    sa.PrimaryKeyConstraint('nod_uuid'),
    sa.UniqueConstraint('application_uuid', 'nod_number', name='uq_e_app_notice_of_deficiency_number')
    )
    op.create_index(op.f('ix_e_app_notice_of_deficiency_nod_uuid'), 'e_app_notice_of_deficiency', ['nod_uuid'], unique=False)
    op.create_index(op.f('ix_e_app_notice_of_deficiency_application_uuid'), 'e_app_notice_of_deficiency', ['application_uuid'], unique=False)
    op.create_index(op.f('ix_e_app_notice_of_deficiency_activity'), 'e_app_notice_of_deficiency', ['activity'], unique=False)
    op.create_index(op.f('ix_e_app_notice_of_deficiency_due_date'), 'e_app_notice_of_deficiency', ['due_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_e_app_notice_of_deficiency_due_date'), table_name='e_app_notice_of_deficiency')
    op.drop_index(op.f('ix_e_app_notice_of_deficiency_activity'), table_name='e_app_notice_of_deficiency')
    op.drop_index(op.f('ix_e_app_notice_of_deficiency_application_uuid'), table_name='e_app_notice_of_deficiency')
    op.drop_index(op.f('ix_e_app_notice_of_deficiency_nod_uuid'), table_name='e_app_notice_of_deficiency')
    op.drop_table('e_app_notice_of_deficiency')
