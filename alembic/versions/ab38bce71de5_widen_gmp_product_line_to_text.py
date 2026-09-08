"""widen GMP_PRODUCT_LINE to Text

Turns gmp_record.GMP_PRODUCT_LINE from VARCHAR(100) into TEXT so the field can
hold a long, multi-line "Product Line / Manufacturing Operation" entry. MySQL
can't keep a plain index on a TEXT column, so the existing index is dropped and
recreated as a 191-char prefix index.

Revision ID: ab38bce71de5
Revises: cabcfd56e5df
Create Date: 2026-09-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "ab38bce71de5"
down_revision: Union[str, Sequence[str], None] = "cabcfd56e5df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEX = "ix_gmp_record_GMP_PRODUCT_LINE"
_NEW_COMMENT = "Product Line / Manufacturing Operation"
_OLD_COMMENT = "Product Line"


def upgrade() -> None:
    op.drop_index(op.f(_INDEX), table_name="gmp_record")
    op.alter_column(
        "gmp_record", "GMP_PRODUCT_LINE",
        existing_type=sa.String(length=100),
        type_=mysql.TEXT(),
        existing_nullable=True,
        existing_comment=_OLD_COMMENT,
        comment=_NEW_COMMENT,
    )
    op.create_index(
        op.f(_INDEX), "gmp_record", ["GMP_PRODUCT_LINE"],
        unique=False, mysql_length=191,
    )


def downgrade() -> None:
    # NOTE: values longer than 100 characters are truncated by MySQL here.
    op.drop_index(op.f(_INDEX), table_name="gmp_record")
    op.alter_column(
        "gmp_record", "GMP_PRODUCT_LINE",
        existing_type=mysql.TEXT(),
        type_=sa.String(length=100),
        existing_nullable=True,
        existing_comment=_NEW_COMMENT,
        comment=_OLD_COMMENT,
    )
    op.create_index(
        op.f(_INDEX), "gmp_record", ["GMP_PRODUCT_LINE"], unique=False,
    )
