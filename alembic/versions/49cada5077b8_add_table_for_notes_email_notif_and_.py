"""add_table for notes,email notif, and attempt

Revision ID: 49cada5077b8
Revises: c48450ab01db
Create Date: 2026-09-29 08:03:48.399233

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "49cada5077b8"
down_revision: Union[str, Sequence[str], None] = "c48450ab01db"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ---------------- new tables ----------------
    op.create_table(
        "cpr_app_notes",
        sa.Column("note_uuid", sa.String(length=36), nullable=False),
        sa.Column("application_uuid", sa.String(length=36), nullable=False),
        sa.Column("author_user_uuid", sa.String(length=36), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("email_requested", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["application_uuid"],
            ["cpr_application.application_uuid"],
        ),
        sa.ForeignKeyConstraint(
            ["author_user_uuid"],
            ["users.user_uuid"],
        ),
        sa.PrimaryKeyConstraint("note_uuid"),
    )
    op.create_index(
        op.f("ix_cpr_app_notes_application_uuid"),
        "cpr_app_notes",
        ["application_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpr_app_notes_note_uuid"), "cpr_app_notes", ["note_uuid"], unique=False
    )
    op.create_table(
        "cpr_generated_documents",
        sa.Column("doc_uuid", sa.String(length=36), nullable=False),
        sa.Column("application_uuid", sa.String(length=36), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("source_uuid", sa.String(length=36), nullable=True),
        sa.Column("drive_file_id", sa.String(length=255), nullable=False),
        sa.Column("drive_file_url", sa.Text(), nullable=False),
        sa.Column("drive_folder_id", sa.String(length=255), nullable=True),
        sa.Column("generated_by_user_uuid", sa.String(length=36), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["application_uuid"],
            ["cpr_application.application_uuid"],
        ),
        sa.ForeignKeyConstraint(
            ["generated_by_user_uuid"],
            ["users.user_uuid"],
        ),
        sa.PrimaryKeyConstraint("doc_uuid"),
    )
    op.create_index(
        op.f("ix_cpr_generated_documents_application_uuid"),
        "cpr_generated_documents",
        ["application_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpr_generated_documents_document_type"),
        "cpr_generated_documents",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpr_generated_documents_source_uuid"),
        "cpr_generated_documents",
        ["source_uuid"],
        unique=False,
    )
    op.create_table(
        "cpr_email_notification",
        sa.Column("notification_uuid", sa.String(length=36), nullable=False),
        sa.Column("application_uuid", sa.String(length=36), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("source_uuid", sa.String(length=36), nullable=True),
        sa.Column("generated_doc_uuid", sa.String(length=36), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["application_uuid"],
            ["cpr_application.application_uuid"],
        ),
        sa.ForeignKeyConstraint(
            ["generated_doc_uuid"],
            ["cpr_generated_documents.doc_uuid"],
        ),
        sa.PrimaryKeyConstraint("notification_uuid"),
    )
    op.create_index(
        op.f("ix_cpr_email_notification_application_uuid"),
        "cpr_email_notification",
        ["application_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpr_email_notification_document_type"),
        "cpr_email_notification",
        ["document_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpr_email_notification_notification_uuid"),
        "cpr_email_notification",
        ["notification_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpr_email_notification_source_uuid"),
        "cpr_email_notification",
        ["source_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpr_email_notification_status"),
        "cpr_email_notification",
        ["status"],
        unique=False,
    )
    op.create_table(
        "cpr_email_notification_attempt",
        sa.Column("attempt_uuid", sa.String(length=36), nullable=False),
        sa.Column("notification_uuid", sa.String(length=36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempted_by_user_uuid", sa.String(length=36), nullable=True),
        sa.Column(
            "attempted_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["attempted_by_user_uuid"],
            ["users.user_uuid"],
        ),
        sa.ForeignKeyConstraint(
            ["notification_uuid"],
            ["cpr_email_notification.notification_uuid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attempt_uuid"),
    )
    op.create_index(
        op.f("ix_cpr_email_notification_attempt_attempt_uuid"),
        "cpr_email_notification_attempt",
        ["attempt_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpr_email_notification_attempt_notification_uuid"),
        "cpr_email_notification_attempt",
        ["notification_uuid"],
        unique=False,
    )

    # ------- cpr_app_documents: uploaded_by_user_id (int) -> uploaded_by_user_uuid -------
    # 1. add the new column
    op.add_column(
        "cpr_app_documents",
        sa.Column("uploaded_by_user_uuid", sa.String(length=36), nullable=True),
    )

    # 2. backfill from users so existing rows keep their uploader
    op.execute("""
        UPDATE cpr_app_documents d
        JOIN users u ON u.id = d.uploaded_by_user_id
        SET d.uploaded_by_user_uuid = u.user_uuid
    """)

    # 3. MySQL order: FK first, then its index, then the column
    op.drop_constraint(
        "cpr_app_documents_ibfk_2", "cpr_app_documents", type_="foreignkey"
    )
    op.drop_index(
        op.f("ix_cpr_app_documents_uploaded_by_user_id"), table_name="cpr_app_documents"
    )
    op.drop_column("cpr_app_documents", "uploaded_by_user_id")

    # 4. new index + named FK
    op.create_index(
        op.f("ix_cpr_app_documents_uploaded_by_user_uuid"),
        "cpr_app_documents",
        ["uploaded_by_user_uuid"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_cpr_app_documents_uploaded_by_user_uuid",
        "cpr_app_documents",
        "users",
        ["uploaded_by_user_uuid"],
        ["user_uuid"],
    )

    # ------- cpr_payment_verification -------
    op.add_column(
        "cpr_payment_verification",
        sa.Column("posting_batch_uuid", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_cpr_payment_verification_posting_batch_uuid"),
        "cpr_payment_verification",
        ["posting_batch_uuid"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # ------- cpr_payment_verification -------
    op.drop_index(
        op.f("ix_cpr_payment_verification_posting_batch_uuid"),
        table_name="cpr_payment_verification",
    )
    op.drop_column("cpr_payment_verification", "posting_batch_uuid")

    # ------- cpr_app_documents: back to uploaded_by_user_id -------
    op.add_column(
        "cpr_app_documents",
        sa.Column(
            "uploaded_by_user_id", mysql.INTEGER(), autoincrement=False, nullable=True
        ),
    )
    op.execute("""
        UPDATE cpr_app_documents d
        JOIN users u ON u.user_uuid = d.uploaded_by_user_uuid
        SET d.uploaded_by_user_id = u.id
    """)
    op.drop_constraint(
        "fk_cpr_app_documents_uploaded_by_user_uuid",
        "cpr_app_documents",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_cpr_app_documents_uploaded_by_user_uuid"),
        table_name="cpr_app_documents",
    )
    op.drop_column("cpr_app_documents", "uploaded_by_user_uuid")
    op.create_index(
        op.f("ix_cpr_app_documents_uploaded_by_user_id"),
        "cpr_app_documents",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "cpr_app_documents_ibfk_2",
        "cpr_app_documents",
        "users",
        ["uploaded_by_user_id"],
        ["id"],
    )

    # ------- new tables (children first) -------
    op.drop_index(
        op.f("ix_cpr_email_notification_attempt_notification_uuid"),
        table_name="cpr_email_notification_attempt",
    )
    op.drop_index(
        op.f("ix_cpr_email_notification_attempt_attempt_uuid"),
        table_name="cpr_email_notification_attempt",
    )
    op.drop_table("cpr_email_notification_attempt")
    op.drop_index(
        op.f("ix_cpr_email_notification_status"), table_name="cpr_email_notification"
    )
    op.drop_index(
        op.f("ix_cpr_email_notification_source_uuid"),
        table_name="cpr_email_notification",
    )
    op.drop_index(
        op.f("ix_cpr_email_notification_notification_uuid"),
        table_name="cpr_email_notification",
    )
    op.drop_index(
        op.f("ix_cpr_email_notification_document_type"),
        table_name="cpr_email_notification",
    )
    op.drop_index(
        op.f("ix_cpr_email_notification_application_uuid"),
        table_name="cpr_email_notification",
    )
    op.drop_table("cpr_email_notification")
    op.drop_index(
        op.f("ix_cpr_generated_documents_source_uuid"),
        table_name="cpr_generated_documents",
    )
    op.drop_index(
        op.f("ix_cpr_generated_documents_document_type"),
        table_name="cpr_generated_documents",
    )
    op.drop_index(
        op.f("ix_cpr_generated_documents_application_uuid"),
        table_name="cpr_generated_documents",
    )
    op.drop_table("cpr_generated_documents")
    op.drop_index(op.f("ix_cpr_app_notes_note_uuid"), table_name="cpr_app_notes")
    op.drop_index(op.f("ix_cpr_app_notes_application_uuid"), table_name="cpr_app_notes")
    op.drop_table("cpr_app_notes")
