"""Add soft delete fields to users.

Revision ID: 20260327_000003
Revises: 20260327_000002
Create Date: 2026-03-27 00:00:03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260327_000003"
down_revision: Union[str, None] = "20260327_000002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.alter_column("users", "is_deleted", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "is_deleted")

