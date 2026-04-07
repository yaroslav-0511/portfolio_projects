"""Drop any FK on invite_codes.activated_by -> users.telegram_id.

Revision ID: 20260327_000004
Revises: 20260327_000003
Create Date: 2026-03-27
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260327_000004"
down_revision: Union[str, None] = "20260327_000003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Be robust to constraint name differences across environments.
    # Drop any FK that constrains invite_codes.activated_by to users.telegram_id.
    bind = op.get_bind()
    inspector = inspect(bind)
    fks = inspector.get_foreign_keys("invite_codes")

    for fk in fks:
        constrained_cols = fk.get("constrained_columns") or []
        referred_table = fk.get("referred_table")
        referred_cols = fk.get("referred_columns") or []
        name = fk.get("name")

        if (
            name
            and constrained_cols == ["activated_by"]
            and referred_table == "users"
            and referred_cols == ["telegram_id"]
        ):
            op.drop_constraint(name, "invite_codes", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        "invite_codes_activated_by_fkey",
        "invite_codes",
        "users",
        ["activated_by"],
        ["telegram_id"],
    )

