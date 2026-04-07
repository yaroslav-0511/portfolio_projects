import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, TelegramObject

from bot.database.models import User
from bot.i18n import t
from bot.services.ui_surface import is_ui_surface_exempt
from bot.states import UI_SURFACE_CID, UI_SURFACE_MID

logger = logging.getLogger(__name__)


class UiSurfaceMiddleware(BaseMiddleware):
    """
    Hard rule: one active inline surface per chat — only callbacks from the
    tracked message (FSM UI_SURFACE_*) are handled. Missing anchor also blocks.
    Exempt: main-menu recovery, notifications, Owner skip, broadcast targets, etc.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)
        cb = event
        if not cb.data or cb.message is None:
            return await handler(event, data)
        if is_ui_surface_exempt(cb.data):
            return await handler(event, data)
        state: FSMContext | None = data.get("state")
        if state is None:
            return await handler(event, data)
        sdata = await state.get_data()
        mid = sdata.get(UI_SURFACE_MID)
        cid = sdata.get(UI_SURFACE_CID)
        db_user: User | None = data.get("db_user")
        lang = db_user.language if db_user and getattr(db_user, "language", None) else "ru"
        if mid is None or cid is None:
            await cb.answer(t("ui_use_latest_message", lang), show_alert=True)
            return None
        if cb.message.chat.id != cid:
            await cb.answer(t("ui_use_latest_message", lang), show_alert=True)
            return None
        if cb.message.message_id == mid:
            return await handler(event, data)
        await cb.answer(t("ui_use_latest_message", lang), show_alert=True)
        return None
