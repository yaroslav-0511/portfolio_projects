
import logging
import secrets

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.database.models import User, UserRole, WellbeingResponse
from bot.database.session import get_session
from bot.i18n import t
from bot.keyboards.user_kb import (
    back_to_menu_keyboard, main_menu_keyboard, self_help_nav_keyboard, who5_scale_keyboard,
    who5_start_keyboard,
)
from bot.services.wellbeing import who5_raw_and_percent, who5_recommendation_key
from bot.services.ui_surface import touch_ui_surface
from bot.states import WellbeingStates

logger = logging.getLogger(__name__)
router = Router(name="wellbeing")

SELF_HELP_PAGES = 3

WHO5_SESSION_KEY = "who5_session_id"


def _require_user(db_user: User | None) -> bool:
    return (
        db_user is not None
        and db_user.role == UserRole.USER
        and not getattr(db_user, "is_deleted", False)
        and not db_user.is_blocked
        and db_user.company_id is not None
    )


@router.callback_query(F.data == "menu:self_help")
async def cb_self_help(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_user(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    await state.clear()
    lang = db_user.language
    text = t("self_help_intro", lang)
    await callback.message.edit_text(
        text,
        reply_markup=self_help_nav_keyboard(lang, 0, SELF_HELP_PAGES),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("self_help:page:"))
async def cb_self_help_page(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_user(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    lang = db_user.language
    page = int(callback.data.split(":")[2])
    page = max(0, min(page, SELF_HELP_PAGES - 1))
    text = t(f"self_help_page_{page + 1}", lang)
    await callback.message.edit_text(
        text,
        reply_markup=self_help_nav_keyboard(lang, page, SELF_HELP_PAGES),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "menu:wellbeing")
async def cb_wellbeing_intro(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_user(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    lang = db_user.language
    await state.clear()
    await callback.message.edit_text(
        t("who5_intro", lang),
        reply_markup=who5_start_keyboard(lang),
        parse_mode="Markdown",
    )
    await state.set_state(WellbeingStates.intro)
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "who5:start", WellbeingStates.intro)
async def cb_who5_start(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_user(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    lang = db_user.language
    session_id = secrets.token_hex(4)
    await state.set_state(WellbeingStates.in_progress)
    await state.update_data(who5_answers=[], **{WHO5_SESSION_KEY: session_id})
    await _show_who5_question(callback, state, lang, 0)
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "who5:start")
async def cb_who5_start_orphan(callback: CallbackQuery, db_user: User | None) -> None:
    if not _require_user(db_user):
        await callback.answer()
        return
    lang = db_user.language
    await callback.answer(t("who5_callback_stale", lang), show_alert=True)


@router.callback_query(F.data.startswith("who5:cancel"), WellbeingStates.in_progress)
async def cb_who5_cancel(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    parts = callback.data.split(":")
    data = await state.get_data()
    sid = data.get(WHO5_SESSION_KEY)
    if len(parts) != 3 or parts[2] != sid:
        lang = db_user.language if db_user else "ru"
        await callback.answer(t("who5_callback_stale", lang), show_alert=True)
        return
    await callback.answer()
    await state.clear()
    if db_user:
        lang = db_user.language
        await callback.message.edit_text(
            t("main_menu", lang),
            reply_markup=main_menu_keyboard(lang),
            parse_mode="Markdown",
        )
        await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("who5:v:"), WellbeingStates.in_progress)
async def cb_who5_value(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_user(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    lang = db_user.language
    parts = callback.data.split(":")
    data = await state.get_data()
    sid = data.get(WHO5_SESSION_KEY)
    answers: list[int] = list(data.get("who5_answers", []))

    if len(parts) != 5 or parts[0] != "who5" or parts[1] != "v":
        await callback.answer(t("who5_callback_stale", lang), show_alert=True)
        return
    token, q_str, val_str = parts[2], parts[3], parts[4]
    if token != sid or sid is None:
        await callback.answer(t("who5_callback_stale", lang), show_alert=True)
        return
    try:
        q_idx = int(q_str)
        val = int(val_str)
    except ValueError:
        await callback.answer(t("who5_callback_stale", lang), show_alert=True)
        return
    if q_idx != len(answers) or val < 0 or val > 5:
        await callback.answer(t("who5_callback_stale", lang), show_alert=True)
        return

    await callback.answer()

    data = await state.get_data()
    sid_live = data.get(WHO5_SESSION_KEY)
    answers = list(data.get("who5_answers", []))
    if sid_live != token or sid_live is None or q_idx != len(answers):
        return

    if len(answers) >= 5:
        await state.clear()
        return

    answers.append(val)
    await state.update_data(who5_answers=answers)

    if len(answers) < 5:
        await _show_who5_question(callback, state, lang, len(answers))
        await touch_ui_surface(state, callback.message)
        return

    raw, percent = who5_raw_and_percent(answers)
    rec_key = who5_recommendation_key(percent)
    telegram_id = callback.from_user.id

    try:
        async with get_session() as session:
            session.add(WellbeingResponse(user_id=telegram_id, score_raw=raw))
    except Exception as e:
        logger.error(f"Wellbeing save failed: {e}")

    body = t("who5_result", lang, raw=raw, percent=percent)
    rec = t(rec_key, lang)
    await callback.message.edit_text(
        f"{body}\n\n{rec}",
        reply_markup=back_to_menu_keyboard(lang),
        parse_mode="Markdown",
    )
    await state.set_state(WellbeingStates.showing_result)
    await state.update_data(who5_answers=[], **{WHO5_SESSION_KEY: None})
    await touch_ui_surface(state, callback.message)


async def _show_who5_question(
    callback: CallbackQuery, state: FSMContext, lang: str, q_index: int
) -> None:
    qn = q_index + 1
    text = t(f"who5_q{qn}", lang)
    data = await state.get_data()
    session_id = data.get(WHO5_SESSION_KEY)
    if not session_id:
        return
    await callback.message.edit_text(
        text,
        reply_markup=who5_scale_keyboard(lang, session_id, q_index),
        parse_mode="Markdown",
    )


@router.callback_query(
    (F.data.startswith("who5:v:")) | (F.data.startswith("who5:cancel")),
    ~StateFilter(WellbeingStates.in_progress),
)
async def cb_who5_orphan_callback(callback: CallbackQuery, db_user: User | None) -> None:
    """Stale taps when WHO-5 is not in the answering state."""
    if not _require_user(db_user):
        await callback.answer()
        return
    lang = db_user.language
    await callback.answer(t("who5_callback_stale", lang), show_alert=True)
