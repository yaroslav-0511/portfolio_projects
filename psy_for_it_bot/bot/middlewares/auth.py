import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from sqlalchemy import select

from bot.config import OWNER_TELEGRAM_IDS
from bot.database.models import User, UserRole
from bot.database.session import get_session

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    Attaches the current User ORM object to handler data['db_user'].
    Automatically creates an Owner record if the telegram_id is in OWNER_TELEGRAM_IDS.
    Also updates last_active_at on every request.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_id: int | None = None

        if isinstance(event, Update):
            if event.message and event.message.from_user:
                telegram_id = event.message.from_user.id
            elif event.callback_query and event.callback_query.from_user:
                telegram_id = event.callback_query.from_user.id

        if telegram_id is None:
            return await handler(event, data)

        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user: User | None = result.scalar_one_or_none()

            if user is None and telegram_id in OWNER_TELEGRAM_IDS:
                user = User(
                    telegram_id=telegram_id,
                    role=UserRole.OWNER,
                    language="ru",
                    company_id=None,
                )
                session.add(user)
                await session.flush()

            if user is not None:
                user.last_active_at = datetime.now(timezone.utc).replace(tzinfo=None)

            data["db_user"] = user
            return await handler(event, data)


class ProxyRelayMiddleware(BaseMiddleware):
    """
    Intercepts regular text/media messages when the sender has an active conversation,
    relaying them to the other party without invoking normal handlers.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update) or not event.message:
            return await handler(event, data)

        msg: Message = event.message

        # Skip commands — let handlers process them
        if msg.text and msg.text.startswith("/"):
            return await handler(event, data)

        telegram_id = msg.from_user.id if msg.from_user else None
        if not telegram_id:
            return await handler(event, data)

        from bot.services.proxy import get_active_conversation, relay_message

        async with get_session() as session:
            conv = await get_active_conversation(session, telegram_id)
            if conv is not None:
                await relay_message(msg, conv, telegram_id, msg.bot)
                return  # Do not call further handlers

        return await handler(event, data)
