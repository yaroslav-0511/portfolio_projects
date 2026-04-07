import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import OWNER_TELEGRAM_IDS
from bot.database.models import (
    Company, CompanyStatus, InviteCode, InviteCodeType, User, UserRole,
)
from bot.database.session import get_session
from bot.i18n import t
from bot.keyboards.user_kb import language_keyboard, main_menu_keyboard
from bot.keyboards.consultant_kb import consultant_main_menu
from bot.keyboards.owner_kb import owner_main_menu
from bot.services.invite import validate_and_activate_code
from bot.services.ui_surface import sync_ui_surface_if_other, touch_ui_surface
from bot.states import OnboardingStates

logger = logging.getLogger(__name__)
router = Router(name="common")


async def _send_main_menu(message: Message, user: User, state: FSMContext) -> None:
    lang = user.language
    if user.role == UserRole.OWNER:
        text = t("owner_main_menu", lang)
        kb = owner_main_menu(lang)
    elif user.role == UserRole.CONSULTANT:
        text = t("consultant_main_menu", lang)
        kb = consultant_main_menu(lang)
    else:
        text = t("main_menu", lang)
        kb = main_menu_keyboard(lang)
    sent = await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await touch_ui_surface(state, sent)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, db_user: User | None) -> None:
    await state.clear()

    # Extract deep-link parameter
    args = message.text.split(maxsplit=1)
    deep_link_code = args[1].strip() if len(args) > 1 else None

    telegram_id = message.from_user.id

    # Owner fast-path
    if telegram_id in OWNER_TELEGRAM_IDS:
        if db_user is None:
            async with get_session() as session:
                db_user = User(
                    telegram_id=telegram_id,
                    role=UserRole.OWNER,
                    language="ru",
                )
                session.add(db_user)
                await session.flush()
        await _send_main_menu(message, db_user, state)
        return

    # Already registered user
    if db_user is not None:
        # Treat deleted accounts OR accounts without a company as new onboarding
        if getattr(db_user, "is_deleted", False) or db_user.company_id is None:
            db_user = None
        else:
            if db_user.is_blocked:
                await message.answer(t("user_blocked", db_user.language))
                return
            if db_user.company_id is not None:
                async with get_session() as session:
                    result = await session.execute(
                        select(Company).where(Company.id == db_user.company_id)
                    )
                    company: Company | None = result.scalar_one_or_none()
                    if company and company.status == CompanyStatus.INACTIVE:
                        await message.answer(t("access_suspended", db_user.language))
                        return
            await _send_main_menu(message, db_user, state)
            return

    # New user — show language selection first
    if deep_link_code:
        # Try to auto-activate via deep link
        await state.update_data(pending_code=deep_link_code)

    sent = await message.answer(t("language_selection", "ru"), reply_markup=language_keyboard())
    await touch_ui_surface(state, sent)


@router.callback_query(F.data.startswith("lang:"))
async def cb_select_language(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    lang = callback.data.split(":")[1]
    await callback.answer()

    if (
        db_user is not None
        and not getattr(db_user, "is_deleted", False)
        and db_user.company_id is not None
    ):
        # User changing language in settings
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == callback.from_user.id)
            )
            u = result.scalar_one_or_none()
            if u:
                u.language = lang
        await callback.message.edit_text(
            t("main_menu", lang),
            reply_markup=main_menu_keyboard(lang) if db_user.role == UserRole.USER else (
                consultant_main_menu(lang) if db_user.role == UserRole.CONSULTANT
                else owner_main_menu(lang)
            ),
            parse_mode="Markdown",
        )
        await touch_ui_surface(state, callback.message)
        return

    # New user - save language and ask for invite code
    await state.update_data(lang=lang)
    fsm_data = await state.get_data()
    pending_code = fsm_data.get("pending_code")

    if pending_code:
        # Try to activate automatically
        await _try_activate_code(callback.message, state, pending_code, lang, callback.from_user.id)
    else:
        await state.set_state(OnboardingStates.waiting_invite_code)
        await callback.message.edit_text(t("welcome_new", lang))
        await callback.message.answer(t("enter_invite_code", lang))
        await touch_ui_surface(state, callback.message)


async def _try_activate_code(
    message: Message, state: FSMContext, raw_code: str, lang: str, telegram_id: int
) -> None:
    """Shared logic: validate code, create user, show menu."""
    try:
        async with get_session() as session:
            success, error_key, invite = await validate_and_activate_code(session, raw_code, telegram_id)

            if not success:
                await message.answer(t(error_key, lang))
                if error_key == "code_invalid":
                    await state.set_state(OnboardingStates.waiting_invite_code)
                    await message.answer(t("enter_invite_code", lang))
                return

            company_result = await session.execute(
                select(Company).where(Company.id == invite.company_id)
            )
            company: Company = company_result.scalar_one()

            if company.status == CompanyStatus.INACTIVE:
                await message.answer(t("access_suspended", lang))
                return

            # Create or reactivate user
            role = UserRole.CONSULTANT if invite.type == InviteCodeType.CONSULTANT else UserRole.USER
            existing_user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            existing_user = existing_user_result.scalar_one_or_none()
            if existing_user:
                existing_user.company_id = company.id
                existing_user.role = role
                existing_user.language = lang
                existing_user.is_blocked = False
                existing_user.is_deleted = False
                existing_user.deleted_at = None
            else:
                new_user = User(
                    telegram_id=telegram_id,
                    company_id=company.id,
                    role=role,
                    language=lang,
                )
                session.add(new_user)
                await session.flush()

            if role == UserRole.CONSULTANT:
                # Consultant profile is created by Owner - just set the role here
                pass

            await state.clear()
            await message.answer(
                t("welcome_success", lang, company=company.name),
                parse_mode="Markdown",
            )

            # Show appropriate menu
            if role == UserRole.USER:
                sent = await message.answer(
                    t("main_menu", lang),
                    reply_markup=main_menu_keyboard(lang),
                    parse_mode="Markdown",
                )
                await touch_ui_surface(state, sent)
            elif role == UserRole.CONSULTANT:
                sent = await message.answer(
                    t("consultant_main_menu", lang),
                    reply_markup=consultant_main_menu(lang),
                    parse_mode="Markdown",
                )
                await touch_ui_surface(state, sent)
    except Exception as e:
        logger.exception(f"Invite activation failed for {telegram_id}: {e}")
        await message.answer(t("error_generic", lang))


@router.message(OnboardingStates.waiting_invite_code)
async def process_invite_code(message: Message, state: FSMContext) -> None:
    raw_code = message.text.strip() if message.text else ""
    telegram_id = message.from_user.id

    fsm_data = await state.get_data()
    lang = fsm_data.get("lang", "ru")

    if not raw_code:
        await message.answer(t("enter_invite_code", lang))
        return

    # Rate limiting (can be disabled for local testing)
    from bot.config import INVITE_RATE_LIMIT_ENABLED, MAX_INVITE_ATTEMPTS, INVITE_ATTEMPT_WINDOW, REDIS_URL
    if not INVITE_RATE_LIMIT_ENABLED:
        await _try_activate_code(message, state, raw_code, lang, telegram_id)
        return
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(REDIS_URL)
        try:
            key = f"invite_attempts:{telegram_id}"
            attempts = await r.incr(key)
            if attempts == 1:
                await r.expire(key, INVITE_ATTEMPT_WINDOW)
            if attempts > MAX_INVITE_ATTEMPTS:
                await message.answer(t("code_rate_limit", lang))
                return
        finally:
            await r.aclose()
    except Exception as e:
        logger.warning(f"Rate limiting unavailable (Redis?): {e}")

    await _try_activate_code(message, state, raw_code, lang, telegram_id)


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    pre_data = await state.get_data()
    await state.clear()
    if db_user is None:
        await callback.message.answer(t("not_registered", "ru"))
        return
    lang = db_user.language
    if db_user.role == UserRole.OWNER:
        text = t("owner_main_menu", lang)
        kb = owner_main_menu(lang)
    elif db_user.role == UserRole.CONSULTANT:
        text = t("consultant_main_menu", lang)
        kb = consultant_main_menu(lang)
    else:
        text = t("main_menu", lang)
        kb = main_menu_keyboard(lang)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await sync_ui_surface_if_other(callback.bot, callback.message, pre_data, text, kb)
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "c_menu:main")
async def cb_consultant_main(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    pre_data = await state.get_data()
    await state.clear()
    if db_user is None:
        await callback.message.answer(t("not_registered", "ru"))
        return
    lang = db_user.language
    text = t("consultant_main_menu", lang)
    kb = consultant_main_menu(lang)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await sync_ui_surface_if_other(callback.bot, callback.message, pre_data, text, kb)
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "o_menu:main")
async def cb_owner_main(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if db_user is None or db_user.role != UserRole.OWNER:
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    pre_data = await state.get_data()
    await state.clear()
    lang = db_user.language
    text = t("owner_main_menu", lang)
    kb = owner_main_menu(lang)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await sync_ui_surface_if_other(callback.bot, callback.message, pre_data, text, kb)
    await touch_ui_surface(state, callback.message)
