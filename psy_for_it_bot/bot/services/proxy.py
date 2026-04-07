import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ActiveConversation, ConversationStatus, User
from bot.i18n import t

logger = logging.getLogger(__name__)


async def get_active_conversation(
    session: AsyncSession, telegram_id: int
) -> ActiveConversation | None:
    """Return an active conversation where telegram_id is either user or consultant."""
    result = await session.execute(
        select(ActiveConversation).where(
            ActiveConversation.status == ConversationStatus.ACTIVE,
            (
                (ActiveConversation.user_id == telegram_id)
                | (ActiveConversation.consultant_telegram_id == telegram_id)
            ),
        )
    )
    return result.scalar_one_or_none()


async def relay_message(
    msg: Message,
    conv: ActiveConversation,
    sender_id: int,
    bot: Bot | None,
) -> None:
    """Forward a message to the other party in the conversation."""
    if bot is None:
        logger.error("Bot instance not available in relay_message")
        return

    is_user = sender_id == conv.user_id
    recipient_id = conv.consultant_telegram_id if is_user else conv.user_id

    # Get recipient language
    from bot.database.session import get_session
    async with get_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == recipient_id))
        recipient_user: User | None = result.scalar_one_or_none()
        lang = recipient_user.language if recipient_user else "ru"

    label = t("proxy_relay_note", lang) if is_user else t("proxy_relay_from_consultant", lang)

    try:
        await bot.send_message(recipient_id, label, parse_mode="Markdown")
        await bot.copy_message(
            chat_id=recipient_id,
            from_chat_id=msg.chat.id,
            message_id=msg.message_id,
        )
    except Exception as e:
        logger.error(f"Relay failed: {e}")


async def start_conversation(
    session: AsyncSession,
    user_id: int,
    consultant_telegram_id: int,
    session_id: int | None = None,
    conv_type: str = "urgent",
) -> ActiveConversation:
    conv = ActiveConversation(
        user_id=user_id,
        consultant_telegram_id=consultant_telegram_id,
        session_id=session_id,
        conv_type=conv_type,
        status=ConversationStatus.ACTIVE,
    )
    session.add(conv)
    await session.flush()
    return conv


async def end_conversation(
    session: AsyncSession, conv_id: int
) -> ActiveConversation | None:
    result = await session.execute(
        select(ActiveConversation).where(ActiveConversation.id == conv_id)
    )
    conv: ActiveConversation | None = result.scalar_one_or_none()
    if conv:
        conv.status = ConversationStatus.ENDED
        conv.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return conv
