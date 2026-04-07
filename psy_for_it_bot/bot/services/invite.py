import random
import string
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Company, InviteCode, InviteCodeStatus, InviteCodeType, User


def _generate_raw_code() -> str:
    chars = string.ascii_uppercase + string.digits
    return (
        "".join(random.choices(chars, k=4))
        + "-"
        + "".join(random.choices(chars, k=4))
        + "-"
        + "".join(random.choices(chars, k=4))
    )


def _hash_code(code: str) -> str:
    return bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()


def _verify_code(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


async def generate_invite_codes(
    session: AsyncSession,
    company: Company,
    count: int,
    code_type: InviteCodeType = InviteCodeType.USER,
    expires_at: datetime | None = None,
) -> list[str]:
    raw_codes = []
    for _ in range(count):
        raw = _generate_raw_code()
        raw_codes.append(raw)
        hashed = _hash_code(raw)
        invite = InviteCode(
            code=raw,
            code_hash=hashed,
            company_id=company.id,
            status=InviteCodeStatus.ACTIVE,
            type=code_type,
            expires_at=expires_at,
        )
        session.add(invite)
    return raw_codes


async def validate_and_activate_code(
    session: AsyncSession,
    raw_code: str,
    telegram_id: int,
) -> tuple[bool, str, InviteCode | None]:
    """
    Returns (success, error_key, invite_code_object).
    error_key is a translation key on failure.
    """
    raw_upper = raw_code.strip().upper()

    result = await session.execute(
        select(InviteCode).where(InviteCode.code == raw_upper)
    )
    invite: InviteCode | None = result.scalar_one_or_none()

    if invite is None:
        return False, "code_invalid", None

    if invite.status == InviteCodeStatus.USED:
        return False, "code_used", None

    if invite.status == InviteCodeStatus.REVOKED:
        return False, "code_revoked", None

    if invite.status == InviteCodeStatus.EXPIRED:
        return False, "code_expired", None

    if invite.expires_at and invite.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        invite.status = InviteCodeStatus.EXPIRED
        return False, "code_expired", None

    # Mark as used
    invite.status = InviteCodeStatus.USED
    invite.activated_by = telegram_id
    invite.activated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    return True, "", invite


async def get_company_active_user_count(session: AsyncSession, company_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(User).where(
            User.company_id == company_id, User.is_blocked.is_(False)
        )
    )
    return result.scalar_one()
