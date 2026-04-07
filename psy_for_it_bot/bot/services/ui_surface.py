"""
Single inline-UI anchor per chat (FSM): prevents acting on stale messages while
keeping exempt auxiliary keyboards (notifications, skip, broadcast targets).
"""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.i18n import t
from bot.states import UI_SURFACE_CID, UI_SURFACE_MID

logger = logging.getLogger(__name__)

_EXEMPT_EXACT = frozenset({"menu:main", "c_menu:main", "o_menu:main", "skip"})

_EXEMPT_PREFIXES = (
    "urgent_accept:",
    "end_conv:",
    "feedback:",
    "feedback_comment:",
    "session_status:",
    "cancel_reason:",
    "reminder:ok:",
    "reminder:reschedule:",
    "broadcast:",
)


def is_ui_surface_exempt(callback_data: str | None) -> bool:
    if callback_data is None:
        return True
    if callback_data in _EXEMPT_EXACT:
        return True
    return any(callback_data.startswith(p) for p in _EXEMPT_PREFIXES)


async def touch_ui_surface(state: FSMContext, message: Message | None) -> None:
    if message is None:
        return
    await state.update_data(
        **{
            UI_SURFACE_MID: message.message_id,
            UI_SURFACE_CID: message.chat.id,
        }
    )


async def retire_ui_surface_if_present(
    bot: Bot,
    chat_id: int,
    pre_clear_state_data: dict,
    db_user_language: str | None,
) -> None:
    """Optional: replace anchor message text and remove its keyboard. Not used on /start anymore."""
    mid = pre_clear_state_data.get(UI_SURFACE_MID)
    cid = pre_clear_state_data.get(UI_SURFACE_CID)
    if mid is None or cid is None or cid != chat_id:
        return
    lang = db_user_language or "ru"
    try:
        await bot.edit_message_text(
            t("ui_stale_prompt", lang),
            chat_id=cid,
            message_id=mid,
            reply_markup=None,
            parse_mode="Markdown",
        )
    except TelegramBadRequest as e:
        logger.debug("UI surface retire skipped: %s", e)


async def sync_ui_surface_if_other(
    bot: Bot,
    clicked_message: Message,
    pre_state_data: dict,
    text: str,
    reply_markup: object,
    parse_mode: str = "Markdown",
) -> None:
    mid = pre_state_data.get(UI_SURFACE_MID)
    cid = pre_state_data.get(UI_SURFACE_CID)
    if mid is None or cid is None:
        return
    if cid != clicked_message.chat.id or mid == clicked_message.message_id:
        return
    try:
        await bot.edit_message_text(
            text,
            chat_id=cid,
            message_id=mid,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except TelegramBadRequest as e:
        logger.debug("UI surface sync skipped: %s", e)
