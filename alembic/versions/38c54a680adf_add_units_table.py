"""Add units table

Revision ID: 38c54a680adf
Revises: 18a3e0f77b26
Create Date: 2026-08-06 11:26:36.234933

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "38c54a680adf"
down_revision: Union[str, Sequence[str], None] = "18a3e0f77b26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lead_user_id", sa.Integer(), nullable=True),
        sa.Column("qa_admin_user_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["lead_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["qa_admin_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_units_id"), "units", ["id"], unique=False)
    op.create_index(
        op.f("ix_units_lead_user_id"), "units", ["lead_user_id"], unique=False
    )
    op.create_index(op.f("ix_units_name"), "units", ["name"], unique=True)
    op.create_index(
        op.f("ix_units_qa_admin_user_id"), "units", ["qa_admin_user_id"], unique=False
    )

    # NOTE: lead_assignments_ibfk_2 and ix_lead_assignments_lead_user_id
    # don't exist in prod's actual schema (schema drift) — nothing to drop.
    # op.drop_constraint("lead_assignments_ibfk_2", "lead_assignments", type_="foreignkey")
    # op.drop_index(op.f("ix_lead_assignments_lead_user_id"), table_name="lead_assignments")

    # === FIX: these columns were missing from the original migration ===
    op.add_column(
        "lead_assignments",
        sa.Column("unit_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "lead_assignments",
        sa.Column("group_id", sa.Integer(), nullable=True),
    )

    op.create_index(
        op.f("ix_lead_assignments_group_id"),
        "lead_assignments",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_assignments_unit_id"),
        "lead_assignments",
        ["unit_id"],
        unique=False,
    )

    op.create_foreign_key(
        None, "lead_assignments", "groups", ["group_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        None, "lead_assignments", "units", ["unit_id"], ["id"], ondelete="CASCADE"
    )

    # NOTE: lead_user_id / lead_role KEPT for now — do NOT drop until
    # unit_id/group_id are backfilled for existing prod rows. Drop in a
    # separate follow-up migration once backfill is confirmed.
    # op.drop_column("lead_assignments", "lead_user_id")
    # op.drop_column("lead_assignments", "lead_role")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, "lead_assignments", type_="foreignkey")
    op.drop_constraint(None, "lead_assignments", type_="foreignkey")
    op.drop_index(op.f("ix_lead_assignments_unit_id"), table_name="lead_assignments")
    op.drop_index(op.f("ix_lead_assignments_group_id"), table_name="lead_assignments")
    op.drop_column("lead_assignments", "group_id")
    op.drop_column("lead_assignments", "unit_id")
    op.drop_index(op.f("ix_units_qa_admin_user_id"), table_name="units")
    op.drop_index(op.f("ix_units_name"), table_name="units")
    op.drop_index(op.f("ix_units_lead_user_id"), table_name="units")
    op.drop_index(op.f("ix_units_id"), table_name="units")
    op.drop_table("units")
