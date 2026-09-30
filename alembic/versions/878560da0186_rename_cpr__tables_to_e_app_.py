"""rename cpr_* tables to e_app_*"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "878560da0186"
down_revision: Union[str, Sequence[str], None] = "49cada5077b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# old_table -> (new_table, [index column suffixes]) ; MySQL 8 RENAME INDEX
RENAMES = {
    "cpr_app_history": ("e_app_history", ["process_uuid", "user_uuid"]),
    "cpr_application": ("e_application", []),
    "cpr_app_documents": (
        "e_app_documents",
        [
            "application_uuid",
            "category_code",
            "id",
            "requirement_code",
            "requirement_group",
            "uploaded_by_user_uuid",
        ],
    ),
    "cpr_generated_documents": (
        "e_app_generated_documents",
        ["application_uuid", "document_type", "source_uuid"],
    ),
    "cpr_app_notes": ("e_app_notes", ["application_uuid", "note_uuid"]),
    "cpr_order_of_payment": (
        "e_app_order_of_payment",
        [
            "application_uuid",
            "op_number",
            "op_type",
            "op_uuid",
            "parent_op_uuid",
            "status",
        ],
    ),
    "cpr_table_of_changes": (
        "e_app_table_of_changes",
        ["application_uuid", "change_uuid"],
    ),
    "cpr_email_notification": (
        "e_app_email_notification",
        [
            "application_uuid",
            "document_type",
            "notification_uuid",
            "source_uuid",
            "status",
        ],
    ),
    "cpr_email_notification_attempt": (
        "e_app_email_notification_attempt",
        ["attempt_uuid", "notification_uuid"],
    ),
    "cpr_payment_verification": (
        "e_app_payment_verification",
        [
            "official_receipt_number",
            "op_uuid",
            "posting_batch_uuid",
            "reference_number",
            "verification_uuid",
        ],
    ),
}

# Mga indexes na bago lang sa e_app_* (wala sa cpr_*)
NEW_INDEXES = [
    (
        "e_app_history",
        ["application_status", "deadline_date", "del_thread", "history_uuid"],
    ),
    ("e_app_documents", ["application_type"]),
]


def upgrade() -> None:
    # 1. Rename tables (FKs are updated automatically by InnoDB)
    for old, (new, _) in RENAMES.items():
        op.rename_table(old, new)

    # 2. Rename indexes
    for old, (new, cols) in RENAMES.items():
        for c in cols:
            op.execute(
                f"ALTER TABLE `{new}` RENAME INDEX `ix_{old}_{c}` TO `ix_{new}_{c}`"
            )

    # 3. Bagong indexes
    for table, cols in NEW_INDEXES:
        for c in cols:
            op.create_index(op.f(f"ix_{table}_{c}"), table, [c], unique=False)

    # 4. Bagong table
    op.create_table(
        "e_app_parties",
        sa.Column("party_uuid", sa.String(length=36), nullable=False),
        sa.Column("application_uuid", sa.String(length=36), nullable=False),
        sa.Column("party_type", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("tin", sa.String(length=50), nullable=True),
        sa.Column("lto_no", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_uuid"],
            ["e_application.application_uuid"],
        ),
        sa.PrimaryKeyConstraint("party_uuid"),
    )
    op.create_index(
        op.f("ix_e_app_parties_party_uuid"),
        "e_app_parties",
        ["party_uuid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_e_app_parties_party_uuid"), table_name="e_app_parties")
    op.drop_table("e_app_parties")

    for table, cols in NEW_INDEXES:
        for c in cols:
            op.drop_index(op.f(f"ix_{table}_{c}"), table_name=table)

    for old, (new, cols) in RENAMES.items():
        for c in cols:
            op.execute(
                f"ALTER TABLE `{new}` RENAME INDEX `ix_{new}_{c}` TO `ix_{old}_{c}`"
            )

    for old, (new, _) in RENAMES.items():
        op.rename_table(new, old)
