from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.database.models import ActiveConversation, ConversationStatus
from bot.services.proxy import end_conversation, get_active_conversation, start_conversation


class _ScalarResult:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


@pytest.mark.asyncio
async def test_get_active_conversation_none() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(None))

    out = await get_active_conversation(session, telegram_id=999)

    assert out is None


@pytest.mark.asyncio
async def test_get_active_conversation_found() -> None:
    conv = ActiveConversation(
        user_id=1,
        consultant_telegram_id=2,
        status=ConversationStatus.ACTIVE,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(conv))

    out = await get_active_conversation(session, telegram_id=1)

    assert out is conv


@pytest.mark.asyncio
async def test_start_conversation_creates_active() -> None:
    session = AsyncMock()
    session.add = MagicMock()  # sync in SQLAlchemy; AsyncMock would leave un-awaited coroutine
    session.flush = AsyncMock()

    conv = await start_conversation(
        session,
        user_id=10,
        consultant_telegram_id=20,
        session_id=5,
        conv_type="urgent",
    )

    assert conv.user_id == 10
    assert conv.consultant_telegram_id == 20
    assert conv.session_id == 5
    assert conv.conv_type == "urgent"
    assert conv.status == ConversationStatus.ACTIVE
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_end_conversation_sets_ended() -> None:
    conv = ActiveConversation(
        id=7,
        user_id=1,
        consultant_telegram_id=2,
        status=ConversationStatus.ACTIVE,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarResult(conv))

    out = await end_conversation(session, conv_id=7)

    assert out is conv
    assert conv.status == ConversationStatus.ENDED
    assert conv.ended_at is not None
