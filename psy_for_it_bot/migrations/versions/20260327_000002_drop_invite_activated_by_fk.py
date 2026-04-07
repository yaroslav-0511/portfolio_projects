"""Drop FK invite_codes.activated_by -> users.telegram_id.

Revision ID: 20260327_000002
Revises: 20260326_000001
Create Date: 2026-03-27 00:00:02
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260327_000002"
down_revision: Union[str, None] = "20260326_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("invite_codes_activated_by_fkey", "invite_codes", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        "invite_codes_activated_by_fkey",
        "invite_codes",
        "users",
        ["activated_by"],
        ["telegram_id"],
    )

