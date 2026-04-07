from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from bot.database.models import InviteCode, InviteCodeStatus, InviteCodeType
from bot.services.invite import validate_and_activate_code


class _Result:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


@pytest.mark.asyncio
async def test_validate_and_activate_code_invalid_code() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(None))

    ok, err, invite = await validate_and_activate_code(session, "bad-code", 123)

    assert ok is False
    assert err == "code_invalid"
    assert invite is None


@pytest.mark.asyncio
async def test_validate_and_activate_code_used_code() -> None:
    invite = InviteCode(
        code="AAAA-BBBB-CCCC",
        code_hash="hash",
        company_id=1,
        status=InviteCodeStatus.USED,
        type=InviteCodeType.USER,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(invite))

    ok, err, activated = await validate_and_activate_code(session, invite.code, 123)

    assert ok is False
    assert err == "code_used"
    assert activated is None


@pytest.mark.asyncio
async def test_validate_and_activate_code_revoked_code() -> None:
    invite = InviteCode(
        code="AAAA-BBBB-CCCC",
        code_hash="hash",
        company_id=1,
        status=InviteCodeStatus.REVOKED,
        type=InviteCodeType.USER,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(invite))

    ok, err, activated = await validate_and_activate_code(session, invite.code, 123)

    assert ok is False
    assert err == "code_revoked"
    assert activated is None


@pytest.mark.asyncio
async def test_validate_and_activate_code_expired_by_status() -> None:
    invite = InviteCode(
        code="AAAA-BBBB-CCCC",
        code_hash="hash",
        company_id=1,
        status=InviteCodeStatus.EXPIRED,
        type=InviteCodeType.USER,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(invite))

    ok, err, activated = await validate_and_activate_code(session, invite.code, 123)

    assert ok is False
    assert err == "code_expired"
    assert activated is None


@pytest.mark.asyncio
async def test_validate_and_activate_code_expired_by_datetime() -> None:
    invite = InviteCode(
        code="AAAA-BBBB-CCCC",
        code_hash="hash",
        company_id=1,
        status=InviteCodeStatus.ACTIVE,
        type=InviteCodeType.USER,
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(invite))

    ok, err, activated = await validate_and_activate_code(session, invite.code, 123)

    assert ok is False
    assert err == "code_expired"
    assert activated is None
    assert invite.status == InviteCodeStatus.EXPIRED


@pytest.mark.asyncio
async def test_validate_and_activate_code_success_sets_usage_fields() -> None:
    invite = InviteCode(
        code="AAAA-BBBB-CCCC",
        code_hash="hash",
        company_id=1,
        status=InviteCodeStatus.ACTIVE,
        type=InviteCodeType.CONSULTANT,
        expires_at=datetime.utcnow() + timedelta(days=1),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(invite))

    ok, err, activated = await validate_and_activate_code(session, invite.code.lower(), 777)

    assert ok is True
    assert err == ""
    assert activated is invite
    assert invite.status == InviteCodeStatus.USED
    assert invite.activated_by == 777
    assert invite.activated_at is not None

