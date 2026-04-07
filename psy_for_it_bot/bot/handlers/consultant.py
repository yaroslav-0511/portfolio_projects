import logging
from datetime import date, datetime, time, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    ActiveConversation, Company, Consultant, ConversationStatus,
    GroupRegistration, ScheduleSlot, Session, SessionStatus, SessionType,
    SupportGroup, User, UserRole,
)
from bot.database.session import get_session
from bot.i18n import t
from bot.services.ui_surface import touch_ui_surface
from bot.keyboards.consultant_kb import (
    accept_urgent_keyboard, consultant_back_keyboard, consultant_main_menu,
    consultant_delete_confirm_keyboard, consultant_settings_keyboard, end_conversation_keyboard, schedule_days_keyboard, schedule_slots_keyboard,
)
from bot.keyboards.user_kb import language_keyboard
from bot.services.consultant_lifecycle import deactivate_consultant_account

logger = logging.getLogger(__name__)
router = Router(name="consultant")


def _require_consultant(db_user: User | None) -> bool:
    return db_user is not None and db_user.role == UserRole.CONSULTANT


async def _get_consultant(session: AsyncSession, user_id: int) -> Consultant | None:
    result = await session.execute(
        select(Consultant).where(Consultant.user_id == user_id)
    )
    return result.scalar_one_or_none()


# ──────────────────────────── Schedule ────────────────────────────

@router.callback_query(F.data == "c_menu:schedule")
async def cb_c_schedule(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_consultant(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    lang = db_user.language
    await callback.message.edit_text(
        t("c_schedule_intro", lang),
        reply_markup=schedule_days_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("c_day:"))
async def cb_c_day(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    day_str = callback.data.split(":")[1]
    telegram_id = callback.from_user.id

    async with get_session() as session:
        consultant = await _get_consultant(session, telegram_id)
        if not consultant:
            return

        selected_date = date.fromisoformat(day_str)
        slots_result = await session.execute(
            select(ScheduleSlot).where(
                ScheduleSlot.consultant_id == consultant.id,
                ScheduleSlot.date == selected_date,
            )
        )
        existing_slots = slots_result.scalars().all()
        booked_times = [s.start_time.strftime("%H:%M") for s in existing_slots]

    display_date = date.fromisoformat(day_str).strftime("%d.%m.%Y")
    await callback.message.edit_text(
        t("c_schedule_day_selected", lang, date=display_date),
        reply_markup=schedule_slots_keyboard(lang, day_str, booked_times),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("c_slot:"))
async def cb_c_toggle_slot(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    parts = callback.data.split(":")
    day_str = parts[1]
    hour_str = parts[2]
    telegram_id = callback.from_user.id

    async with get_session() as session:
        consultant = await _get_consultant(session, telegram_id)
        if not consultant:
            return

        selected_date = date.fromisoformat(day_str)
        start_t = time.fromisoformat(hour_str)
        end_t = time(start_t.hour + 1, 0)

        slot_result = await session.execute(
            select(ScheduleSlot).where(
                ScheduleSlot.consultant_id == consultant.id,
                ScheduleSlot.date == selected_date,
                ScheduleSlot.start_time == start_t,
            )
        )
        existing_slot: ScheduleSlot | None = slot_result.scalar_one_or_none()

        if existing_slot:
            if existing_slot.is_booked:
                await callback.answer(t("error_generic", lang), show_alert=True)
                return
            await session.delete(existing_slot)
        else:
            new_slot = ScheduleSlot(
                consultant_id=consultant.id,
                date=selected_date,
                start_time=start_t,
                end_time=end_t,
            )
            session.add(new_slot)

        await session.flush()

        # Refresh booked times within same session
        slots_result = await session.execute(
            select(ScheduleSlot).where(
                ScheduleSlot.consultant_id == consultant.id,
                ScheduleSlot.date == selected_date,
            )
        )
        all_slots = slots_result.scalars().all()
        booked_times = [s.start_time.strftime("%H:%M") for s in all_slots]

    display_date = date.fromisoformat(day_str).strftime("%d.%m.%Y")
    await callback.message.edit_text(
        t("c_schedule_day_selected", lang, date=display_date),
        reply_markup=schedule_slots_keyboard(lang, day_str, booked_times),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("c_save:"))
async def cb_c_save_schedule(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    await callback.message.edit_text(
        t("c_schedule_saved", lang),
        reply_markup=schedule_days_keyboard(lang),
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "c_copy_week")
async def cb_c_copy_week(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    telegram_id = callback.from_user.id

    async with get_session() as session:
        consultant = await _get_consultant(session, telegram_id)
        if not consultant:
            return

        today = date.today()
        # Calculate last week's Monday correctly
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)

        last_week_slots_result = await session.execute(
            select(ScheduleSlot).where(
                ScheduleSlot.consultant_id == consultant.id,
                ScheduleSlot.date >= last_monday,
                ScheduleSlot.date < last_monday + timedelta(days=7),
            )
        )
        last_week_slots = last_week_slots_result.scalars().all()

        for slot in last_week_slots:
            days_offset = (slot.date - last_monday).days
            new_date = this_monday + timedelta(days=days_offset)
            existing = await session.execute(
                select(ScheduleSlot).where(
                    ScheduleSlot.consultant_id == consultant.id,
                    ScheduleSlot.date == new_date,
                    ScheduleSlot.start_time == slot.start_time,
                )
            )
            if existing.scalar_one_or_none() is None:
                new_slot = ScheduleSlot(
                    consultant_id=consultant.id,
                    date=new_date,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                )
                session.add(new_slot)

        await session.flush()

    await callback.message.edit_text(
        t("c_schedule_copy_week", lang),
        reply_markup=schedule_days_keyboard(lang),
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Urgent requests ────────────────────────────

@router.callback_query(F.data == "c_menu:urgent")
async def cb_c_urgent_list(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language

    async with get_session() as session:
        urgent_result = await session.execute(
            select(Session).where(
                Session.type == SessionType.URGENT,
                Session.status == SessionStatus.PENDING,
                Session.consultant_id.is_(None),
            ).order_by(Session.created_at.asc())
        )
        urgent_sessions = urgent_result.scalars().all()

    if not urgent_sessions:
        await callback.message.edit_text(
            t("c_urgent_none", lang),
            reply_markup=consultant_back_keyboard(lang),
        )
        await touch_ui_surface(state, callback.message)
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for s in urgent_sessions:
        label = f"🚨 #{s.id} — {s.created_at.strftime('%H:%M %d.%m')}"
        builder.button(text=label, callback_data=f"urgent_accept:{s.id}")
    builder.button(text=t("btn_main_menu", lang), callback_data="c_menu:main")
    builder.adjust(1)

    await callback.message.edit_text(
        t("btn_c_urgent", lang),
        reply_markup=builder.as_markup(),
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("urgent_accept:"))
async def cb_accept_urgent(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    session_id = int(callback.data.split(":")[1])
    telegram_id = callback.from_user.id

    async with get_session() as session:
        consultant = await _get_consultant(session, telegram_id)
        if not consultant:
            return

        sess_result = await session.execute(
            select(Session).where(Session.id == session_id)
        )
        urgent_sess: Session | None = sess_result.scalar_one_or_none()

        if urgent_sess is None:
            await callback.answer(t("error_generic", lang), show_alert=True)
            return

        if urgent_sess.consultant_id is not None:
            await callback.message.edit_text(t("urgent_accepted_by_other", lang))
            await touch_ui_surface(state, callback.message)
            return

        urgent_sess.consultant_id = consultant.id
        urgent_sess.status = SessionStatus.CONFIRMED

        from bot.services.proxy import start_conversation
        conv = await start_conversation(
            session,
            user_id=urgent_sess.user_id,
            consultant_telegram_id=telegram_id,
            session_id=session_id,
            conv_type="urgent",
        )

        user_lang = "ru"
        user_result = await session.execute(select(User).where(User.telegram_id == urgent_sess.user_id))
        user_obj = user_result.scalar_one_or_none()
        if user_obj:
            user_lang = user_obj.language

        # Fetch other consultants within same session
        all_consultants_result = await session.execute(
            select(Consultant).where(
                Consultant.is_active.is_(True),
                Consultant.user_id != telegram_id,
            )
        )
        other_consultants = all_consultants_result.scalars().all()

    await callback.message.edit_text(
        t("urgent_connected", lang),
        reply_markup=end_conversation_keyboard(lang, conv.id),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)

    try:
        await callback.bot.send_message(
            urgent_sess.user_id,
            t("urgent_connected", user_lang),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Failed to notify user about urgent accept: {e}")

    for c in other_consultants:
        try:
            await callback.bot.send_message(
                c.user_id,
                t("urgent_accepted_by_other", "ru"),
            )
        except Exception as e:
            logger.warning(f"Failed to notify consultant {c.user_id} about urgent accept: {e}")


@router.callback_query(F.data.startswith("end_conv:"))
async def cb_end_conversation(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    conv_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        from bot.services.proxy import end_conversation
        conv = await end_conversation(session, conv_id)
        if not conv:
            await callback.message.edit_text(t("error_generic", lang))
            await touch_ui_surface(state, callback.message)
            return

        user_lang = "ru"
        user_result = await session.execute(select(User).where(User.telegram_id == conv.user_id))
        user_obj = user_result.scalar_one_or_none()
        if user_obj:
            user_lang = user_obj.language

        urgent_session_id = conv.session_id

    await callback.message.edit_text(
        t("conversation_ended_consultant", lang),
        reply_markup=consultant_back_keyboard(lang),
    )
    await touch_ui_surface(state, callback.message)

    from bot.keyboards.user_kb import feedback_keyboard
    try:
        await callback.bot.send_message(
            conv.user_id,
            t("conversation_ended_user", user_lang),
            parse_mode="Markdown",
        )
        if urgent_session_id:
            await callback.bot.send_message(
                conv.user_id,
                t("feedback_request", user_lang),
                reply_markup=feedback_keyboard(user_lang, urgent_session_id),
            )
    except Exception as e:
        logger.error(f"Failed to send feedback prompt to user: {e}")


# ──────────────────────────── My sessions (consultant) ────────────────────────────

@router.callback_query(F.data == "c_menu:sessions")
async def cb_c_sessions(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    telegram_id = callback.from_user.id

    async with get_session() as session:
        consultant = await _get_consultant(session, telegram_id)
        if not consultant:
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        sessions_result = await session.execute(
            select(Session).where(
                Session.consultant_id == consultant.id,
                Session.scheduled_at >= now,
                Session.status.in_([SessionStatus.PENDING, SessionStatus.CONFIRMED]),
            ).order_by(Session.scheduled_at.asc()).limit(10)
        )
        sessions = sessions_result.scalars().all()

        if not sessions:
            await callback.message.edit_text(
                t("c_sessions_empty", lang),
                reply_markup=consultant_back_keyboard(lang),
            )
            await touch_ui_surface(state, callback.message)
            return

        # Batch load user and company data
        user_ids = [s.user_id for s in sessions]
        users_result = await session.execute(
            select(User).where(User.telegram_id.in_(user_ids))
        )
        users_map = {u.telegram_id: u for u in users_result.scalars().all()}

        company_ids = {u.company_id for u in users_map.values() if u.company_id}
        companies_map: dict[int, Company] = {}
        if company_ids:
            companies_result = await session.execute(
                select(Company).where(Company.id.in_(company_ids))
            )
            companies_map = {c.id: c for c in companies_result.scalars().all()}

    lines = [t("c_sessions_header", lang)]
    for s in sessions:
        date_str = s.scheduled_at.strftime("%d.%m.%Y") if s.scheduled_at else "—"
        time_str = s.scheduled_at.strftime("%H:%M") if s.scheduled_at else "—"

        user_obj = users_map.get(s.user_id)
        company_name = "Unknown"
        if user_obj and user_obj.company_id:
            comp = companies_map.get(user_obj.company_id)
            if comp:
                company_name = comp.name

        short_req = (s.request_text or "")[:50]
        lines.append(t("c_session_line", lang,
                       date=date_str, time=time_str,
                       company=company_name, request=short_req))

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=consultant_back_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── My groups (consultant) ────────────────────────────

@router.callback_query(F.data == "c_menu:groups")
async def cb_c_groups(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    telegram_id = callback.from_user.id

    async with get_session() as session:
        consultant = await _get_consultant(session, telegram_id)
        if not consultant:
            return

        groups_result = await session.execute(
            select(SupportGroup).where(
                SupportGroup.consultant_id == consultant.id,
                SupportGroup.is_active.is_(True),
            )
        )
        groups = groups_result.scalars().all()

        if not groups:
            await callback.message.edit_text(
                t("c_groups_empty", lang),
                reply_markup=consultant_back_keyboard(lang),
            )
            await touch_ui_surface(state, callback.message)
            return

        # Batch count registrations
        group_ids = [g.id for g in groups]
        counts_result = await session.execute(
            select(GroupRegistration.group_id, func.count().label("cnt"))
            .where(GroupRegistration.group_id.in_(group_ids))
            .group_by(GroupRegistration.group_id)
        )
        counts_map = {row.group_id: row.cnt for row in counts_result}

    lines = []
    for g in groups:
        name = getattr(g, f"name_{lang}", g.name_ru)
        count = counts_map.get(g.id, 0)
        lines.append(t("o_group_line", lang, name=name, count=count))

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=consultant_back_keyboard(lang),
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Statistics ────────────────────────────

@router.callback_query(F.data == "c_menu:stats")
async def cb_c_stats(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        return
    lang = db_user.language
    telegram_id = callback.from_user.id

    async with get_session() as session:
        consultant = await _get_consultant(session, telegram_id)
        if not consultant:
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)

        def count_q(from_dt: datetime):
            return select(func.count()).select_from(Session).where(
                Session.consultant_id == consultant.id,
                Session.status == SessionStatus.COMPLETED,
                Session.scheduled_at >= from_dt,
            )

        week_count = (await session.execute(count_q(week_start))).scalar_one()
        month_count = (await session.execute(count_q(month_start))).scalar_one()
        total_count = (await session.execute(
            select(func.count()).select_from(Session).where(
                Session.consultant_id == consultant.id,
                Session.status == SessionStatus.COMPLETED,
            )
        )).scalar_one()

    await callback.message.edit_text(
        t("c_stats", lang, week=week_count, month=month_count, total=total_count),
        reply_markup=consultant_back_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Settings (consultant) ────────────────────────────

@router.callback_query(F.data == "c_menu:settings")
async def cb_c_settings(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    lang = db_user.language
    await callback.message.edit_text(
        t("settings_menu", lang),
        reply_markup=consultant_settings_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "c_settings:delete")
async def cb_c_delete_account_prompt(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    lang = db_user.language
    await callback.message.edit_text(
        t("delete_account_confirm", lang),
        reply_markup=consultant_delete_confirm_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "c_settings:delete_confirm")
async def cb_c_delete_account_confirm(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_consultant(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    lang = db_user.language
    telegram_id = callback.from_user.id

    async with get_session() as session:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        consultant = await _get_consultant(session, telegram_id)
        groups: list[SupportGroup] = []
        future_sessions: list[Session] = []
        if consultant:
            groups_result = await session.execute(
                select(SupportGroup).where(SupportGroup.consultant_id == consultant.id)
            )
            groups = groups_result.scalars().all()

            future_sessions_result = await session.execute(
                select(Session).where(
                    Session.consultant_id == consultant.id,
                    Session.scheduled_at.is_not(None),
                    Session.scheduled_at > now,
                    Session.status.in_([SessionStatus.PENDING, SessionStatus.CONFIRMED]),
                )
            )
            future_sessions = future_sessions_result.scalars().all()

        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user_obj = user_result.scalar_one_or_none()
        deactivate_consultant_account(
            consultant=consultant,
            user_obj=user_obj,
            groups=groups,
            future_sessions=future_sessions,
            now=now,
        )

    await callback.message.edit_text(t("account_deleted", lang))
    sent = await callback.message.answer(
        t("language_selection", "ru"),
        reply_markup=language_keyboard(),
    )
    await touch_ui_surface(state, sent)
