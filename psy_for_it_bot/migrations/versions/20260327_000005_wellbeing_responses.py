"""Add wellbeing_responses for WHO-5 checks.

Revision ID: 20260327_000005
Revises: 20260327_000004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260327_000005"
down_revision: Union[str, None] = "20260327_000004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wellbeing_responses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("score_raw", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_wellbeing_responses_user_id", "wellbeing_responses", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_wellbeing_responses_user_id", table_name="wellbeing_responses")
    op.drop_table("wellbeing_responses")
