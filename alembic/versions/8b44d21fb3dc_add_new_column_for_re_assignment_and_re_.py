"""Add new column for re-assignment and re-route and doctrack remarks

Revision ID: 8b44d21fb3dc
Revises: aa9353fa9f99
Create Date: 2026-04-22 02:46:21.276243

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b44d21fb3dc'
down_revision: Union[str, Sequence[str], None] = 'aa9353fa9f99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('application_logs')]

    columns_to_add = {
        'doctrack_remarks': sa.Text(),
        'reassigned_by_user_id': sa.Integer(),
        'reassigned_by_user_name': sa.String(length=255),
        'reassigned_at': sa.DateTime(),
        'reassigned_from_user_id': sa.Integer(),
        'reassigned_from_user_name': sa.String(length=255),
        'reassigned_to_user_id': sa.Integer(),
        'reassigned_to_user_name': sa.String(length=255),
        'reassignment_reason': sa.String(length=255),
        'reassignment_remarks': sa.Text(),
        'rerouted_by_user_id': sa.Integer(),
        'rerouted_by_user_name': sa.String(length=255),
        'rerouted_at': sa.DateTime(),
        'reroute_from_step': sa.String(length=255),
        'reroute_target_step': sa.String(length=255),
        'reroute_reason': sa.String(length=255),
        'reroute_remarks': sa.Text(),
    }

    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            op.add_column('application_logs', sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = [col['name'] for col in inspector.get_columns('application_logs')]

    columns_to_drop = [
        'reroute_remarks', 'reroute_reason', 'reroute_target_step',
        'reroute_from_step', 'rerouted_at', 'rerouted_by_user_name',
        'rerouted_by_user_id', 'reassignment_remarks', 'reassignment_reason',
        'reassigned_to_user_name', 'reassigned_to_user_id', 'reassigned_from_user_name',
        'reassigned_from_user_id', 'reassigned_at', 'reassigned_by_user_name',
        'reassigned_by_user_id', 'doctrack_remarks'
    ]

    for col in columns_to_drop:
        if col in existing_columns:
            op.drop_column('application_logs', col)