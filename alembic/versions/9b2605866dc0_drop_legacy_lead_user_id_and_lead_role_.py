"""drop legacy lead_user_id and lead_role, enforce unit_id group_id not null

Revision ID: 9b2605866dc0
Revises: 38c54a680adf
Create Date: 2026-08-18 14:45:11.702937

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9b2605866dc0"
down_revision: Union[str, Sequence[str], None] = "38c54a680adf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {
        col["name"] for col in inspector.get_columns("lead_assignments")
    }
    existing_fks = {
        fk["name"] for fk in inspector.get_foreign_keys("lead_assignments")
    }

    # ── drop legacy columns (conditional: some envs already had these
    #    dropped manually outside of alembic, e.g. dev) ──
    if "lead_user_id" in existing_columns:
        if "lead_assignments_ibfk_2" in existing_fks:
            op.drop_constraint(
                "lead_assignments_ibfk_2", "lead_assignments", type_="foreignkey"
            )
        op.drop_column("lead_assignments", "lead_user_id")
    if "lead_role" in existing_columns:
        op.drop_column("lead_assignments", "lead_role")

    # ── enforce NOT NULL (verified: walang existing NULL sa prod) ──
    op.alter_column(
        "lead_assignments",
        "unit_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "lead_assignments",
        "group_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # ── revert NOT NULL back to nullable ──
    op.alter_column(
        "lead_assignments",
        "group_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "lead_assignments",
        "unit_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # ── restore legacy columns (conditional, walang data na maibabalik,
    #    structure lang) ──
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {
        col["name"] for col in inspector.get_columns("lead_assignments")
    }

    if "lead_role" not in existing_columns:
        op.add_column(
            "lead_assignments",
            sa.Column("lead_role", sa.String(length=100), nullable=True),
        )
    if "lead_user_id" not in existing_columns:
        op.add_column(
            "lead_assignments",
            sa.Column("lead_user_id", sa.Integer(), nullable=True),
        )