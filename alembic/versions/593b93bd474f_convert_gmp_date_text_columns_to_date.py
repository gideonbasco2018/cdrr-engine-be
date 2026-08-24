"""convert gmp date text columns to Date

Revision ID: 593b93bd474f
Revises: ffcfbc5aacbc
Create Date: 2026-07-20 02:14:04.288091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from dateutil import parser as dateutil_parser

# revision identifiers, used by Alembic.
revision: str = '593b93bd474f'
down_revision: Union[str, Sequence[str], None] = 'ffcfbc5aacbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATE_COLUMNS = [
    "GMP_DATE_RECEIVED", "GMP_RELEASED_DATE", "GMP_END_DATE",
    "GMP_NOD_DATE_1", "GMP_NOD_DATE_2", "GMP_NOD_DATE_3",
    "GMP_NOD_DATE_4", "GMP_NOD_DATE_5",
    "GMP_DATE_PRINTED", "GMP_COMPLIANCE_DOCS_DATE_RECEIVED",
]

COMMENTS = {
    "GMP_DATE_RECEIVED": "Date Received",
    "GMP_RELEASED_DATE": "Released Date",
    "GMP_END_DATE": "End Date",
    "GMP_NOD_DATE_1": "1st Date of NOD",
    "GMP_NOD_DATE_2": "2nd Date of NOD",
    "GMP_NOD_DATE_3": "3rd Date of NOD",
    "GMP_NOD_DATE_4": "4th Date of NOD",
    "GMP_NOD_DATE_5": "5th Date of NOD",
    "GMP_DATE_PRINTED": "Date Printed",
    "GMP_COMPLIANCE_DOCS_DATE_RECEIVED": "Compliance / Additional Docs Date Received",
}


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # 1. Add temporary Date columns alongside the existing Text ones
    for col in DATE_COLUMNS:
        op.add_column(
            "gmp_record",
            sa.Column(f"{col}_tmp", sa.Date(), nullable=True, comment=COMMENTS[col]),
        )

    # 2. Read existing text values, parse with dateutil (handles inconsistent formats),
    #    write parsed dates into the temp columns. Unparseable values become NULL.
    rows = conn.execute(sa.text(
        f"SELECT GMP_ID, {', '.join(DATE_COLUMNS)} FROM gmp_record"
    )).fetchall()

    unparsed_log = []
    for row in rows:
        updates = {}
        for col in DATE_COLUMNS:
            raw = row._mapping[col]
            if raw and str(raw).strip():
                try:
                    updates[f"{col}_tmp"] = dateutil_parser.parse(str(raw), fuzzy=True).date()
                except Exception:
                    updates[f"{col}_tmp"] = None
                    unparsed_log.append((row._mapping["GMP_ID"], col, raw))
        if updates:
            set_clause = ", ".join(f"{k} = :{k}" for k in updates)
            conn.execute(
                sa.text(f"UPDATE gmp_record SET {set_clause} WHERE GMP_ID = :id"),
                {**updates, "id": row._mapping["GMP_ID"]},
            )

    if unparsed_log:
        print(f"\n⚠️  {len(unparsed_log)} value(s) could not be parsed and were set to NULL:")
        for gmp_id, col, raw in unparsed_log[:30]:
            print(f"   GMP_ID={gmp_id}  {col}={raw!r}")
        if len(unparsed_log) > 30:
            print(f"   ...and {len(unparsed_log) - 30} more")

    # 3. Drop the old Text columns, rename the temp Date columns into their place
    for col in DATE_COLUMNS:
        op.drop_column("gmp_record", col)
        op.alter_column(
            "gmp_record", f"{col}_tmp",
            new_column_name=col,
            existing_type=sa.Date(),
            existing_comment=COMMENTS[col],
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Reverts column TYPE back to Text. Note: original raw text values are
    # NOT restored — only the parsed date values (as ISO strings) will remain.
    for col in DATE_COLUMNS:
        op.alter_column(
            "gmp_record", col,
            existing_type=sa.Date(),
            type_=mysql.TEXT(),
            existing_comment=COMMENTS[col],
            existing_nullable=True,
        )