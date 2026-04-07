import logging
from datetime import date, datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    ActiveConversation, Company, CompanyStatus, Consultant, ConversationStatus,
    Feedback, GroupRegistration, ScheduleSlot, Session, SessionStatus,
    SessionType, SupportGroup, User, UserRole,
)
from bot.database.session import get_session
from bot.i18n import t
from bot.services.ui_surface import touch_ui_surface
from bot.keyboards.user_kb import (
    back_to_menu_keyboard, delete_confirm_keyboard, feedback_comment_keyboard,
    feedback_keyboard, group_detail_keyboard, groups_keyboard, language_keyboard,
    main_menu_keyboard, cancel_reason_keyboard, settings_keyboard, session_confirm_keyboard,
    slots_keyboard, my_sessions_keyboard,
)
from bot.states import FeedbackStates, SessionBookingStates

logger = logging.getLogger(__name__)
router = Router(name="user")


def _require_user(db_user: User | None) -> bool:
    return (
        db_user is not None
        and db_user.role == UserRole.USER
        and not getattr(db_user, "is_deleted", False)
        and not db_user.is_blocked
        and db_user.company_id is not None
    )


# ──────────────────────────── Emergency ────────────────────────────

@router.callback_query(F.data == "menu:emergency")
async def cb_emergency(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_user(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    await state.clear()
    lang = db_user.language
    telegram_id = callback.from_user.id

    async with get_session() as session:
        # Check if there's already an active conversation
        conv_result = await session.execute(
            select(ActiveConversation).where(
                ActiveConversation.user_id == telegram_id,
                ActiveConversation.status == ConversationStatus.ACTIVE,
            )
        )
        existing_conv = conv_result.scalar_one_or_none()
        if existing_conv:
            await callback.message.edit_text(t("emergency_already_active", lang))
            await touch_ui_surface(state, callback.message)
            return

        # Create a pending urgent session
        new_session = Session(
            user_id=telegram_id,
            type=SessionType.URGENT,
            status=SessionStatus.PENDING,
        )
        session.add(new_session)
        await session.flush()

        # Get company name for notification
        company_name = "Unknown"
        if db_user.company_id:
            comp_result = await session.execute(
                select(Company).where(Company.id == db_user.company_id)
            )
            comp: Company | None = comp_result.scalar_one_or_none()
            if comp:
                company_name = comp.name

        # Get all active consultants
        consultants_result = await session.execute(
            select(Consultant).where(Consultant.is_active.is_(True))
        )
        consultants = consultants_result.scalars().all()

        await callback.message.edit_text(t("emergency_sent", lang), parse_mode="Markdown")
        await touch_ui_surface(state, callback.message)

        # Notify all consultants
        from bot.keyboards.consultant_kb import accept_urgent_keyboard
        notify_text = t(
            "emergency_notify_consultants",
            "ru",
            company=company_name,
            time=datetime.now(timezone.utc).strftime("%H:%M %d.%m.%Y"),
        )
        for consultant in consultants:
            try:
                kb = accept_urgent_keyboard("ru", new_session.id)
                await callback.bot.send_message(
                    consultant.user_id,
                    notify_text,
                    reply_markup=kb,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to notify consultant {consultant.user_id}: {e}")


# ──────────────────────────── Session booking ────────────────────────────

@router.callback_query(F.data == "menu:session")
async def cb_session_menu(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_user(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    lang = db_user.language
    await state.clear()
    await state.set_state(SessionBookingStates.writing_request)
    await callback.message.edit_text(t("session_intro", lang), parse_mode="Markdown")
    await touch_ui_surface(state, callback.message)


@router.message(SessionBookingStates.writing_request)
async def process_session_request(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_user(db_user):
        return
    lang = db_user.language
    request_text = message.text or ""

    if len(request_text) > 500:
        await message.answer(t("session_request_too_long", lang))
        return

    await state.update_data(request_text=request_text)

    async with get_session() as session:
        today = date.today()
        slots_result = await session.execute(
            select(ScheduleSlot)
            .join(Consultant, Consultant.id == ScheduleSlot.consultant_id)
            .where(
                ScheduleSlot.date >= today,
                ScheduleSlot.is_booked.is_(False),
                Consultant.is_active.is_(True),
            )
            .order_by(ScheduleSlot.date, ScheduleSlot.start_time)
            .limit(20)
        )
        slots = slots_result.scalars().all()

    if not slots:
        sent = await message.answer(
            t("session_no_slots", lang), reply_markup=back_to_menu_keyboard(lang)
        )
        await state.clear()
        await touch_ui_surface(state, sent)
        return

    await state.set_state(SessionBookingStates.choosing_slot)
    sent = await message.answer(
        t("session_choose_slot", lang), reply_markup=slots_keyboard(slots, lang)
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data.startswith("slot:"), SessionBookingStates.choosing_slot)
async def cb_choose_slot(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_user(db_user):
        return
    lang = db_user.language
    slot_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        slot_result = await session.execute(
            select(ScheduleSlot).where(ScheduleSlot.id == slot_id)
        )
        slot: ScheduleSlot | None = slot_result.scalar_one_or_none()

        if slot is None or slot.is_booked:
            await callback.message.edit_text(t("session_slot_taken", lang))
            await touch_ui_surface(state, callback.message)
            return

    fsm_data = await state.get_data()
    request_text = fsm_data.get("request_text", "")
    is_reschedule = bool(fsm_data.get("reschedule_session_id"))

    date_str = slot.date.strftime("%d.%m.%Y")
    time_str = slot.start_time.strftime("%H:%M")
    short_request = request_text[:100] + "..." if len(request_text) > 100 else request_text
    if is_reschedule and not short_request:
        short_request = "—"

    await state.update_data(slot_id=slot_id)
    await state.set_state(SessionBookingStates.confirming)

    text = t("session_confirm_prompt", lang, date=date_str, time=time_str, request=short_request)
    await callback.message.edit_text(
        text,
        reply_markup=session_confirm_keyboard(lang, slot_id),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("session:confirm:"))
async def cb_confirm_session(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_user(db_user):
        return
    lang = db_user.language
    slot_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id
    fsm_data = await state.get_data()
    request_text = fsm_data.get("request_text", "")
    reschedule_session_id = fsm_data.get("reschedule_session_id")

    async with get_session() as session:
        if reschedule_session_id:
            # Reschedule existing session: release old slot, book new slot, update reminders
            sess_result = await session.execute(
                select(Session).where(Session.id == int(reschedule_session_id), Session.user_id == telegram_id).with_for_update()
            )
            existing_sess: Session | None = sess_result.scalar_one_or_none()
            if existing_sess is None:
                await callback.message.edit_text(t("error_generic", lang), reply_markup=back_to_menu_keyboard(lang))
                await state.clear()
                await touch_ui_surface(state, callback.message)
                return

            new_slot_result = await session.execute(
                select(ScheduleSlot).where(ScheduleSlot.id == slot_id).with_for_update()
            )
            new_slot: ScheduleSlot | None = new_slot_result.scalar_one_or_none()
            if new_slot is None or new_slot.is_booked:
                await callback.message.edit_text(t("session_slot_taken", lang))
                await state.clear()
                await touch_ui_surface(state, callback.message)
                return

            # Release previous slot (if any)
            if existing_sess.slot_id:
                old_slot_result = await session.execute(
                    select(ScheduleSlot).where(ScheduleSlot.id == existing_sess.slot_id).with_for_update()
                )
                old_slot = old_slot_result.scalar_one_or_none()
                if old_slot:
                    old_slot.is_booked = False

            # Book new slot and update session
            new_slot.is_booked = True
            scheduled_at = datetime.combine(new_slot.date, new_slot.start_time)
            existing_sess.slot_id = slot_id
            existing_sess.consultant_id = new_slot.consultant_id
            existing_sess.scheduled_at = scheduled_at
            existing_sess.status = SessionStatus.CONFIRMED
            existing_sess.confirmed_by_user = True

            await session.flush()

            date_str = new_slot.date.strftime("%d.%m.%Y")
            time_str = new_slot.start_time.strftime("%H:%M")

            await state.clear()
            await callback.message.edit_text(
                t("session_confirmed", lang, date=date_str, time=time_str),
                parse_mode="Markdown",
            )
            await touch_ui_surface(state, callback.message)

            # Re-schedule reminders
            try:
                from bot.services.scheduler import cancel_session_jobs, schedule_session_reminders
                from bot.config import BOT_TOKEN
                cancel_session_jobs(existing_sess.id)
                await schedule_session_reminders(
                    BOT_TOKEN, telegram_id, existing_sess.id,
                    scheduled_at, time_str, lang
                )
            except Exception as e:
                logger.error(f"Failed to reschedule reminders: {e}")

            return

        slot_result = await session.execute(
            select(ScheduleSlot).where(ScheduleSlot.id == slot_id).with_for_update()
        )
        slot: ScheduleSlot | None = slot_result.scalar_one_or_none()

        if slot is None or slot.is_booked:
            await callback.message.edit_text(t("session_slot_taken", lang))
            await state.clear()
            await touch_ui_surface(state, callback.message)
            return

        slot.is_booked = True

        scheduled_at = datetime.combine(slot.date, slot.start_time)
        new_session = Session(
            user_id=telegram_id,
            consultant_id=slot.consultant_id,
            slot_id=slot_id,
            type=SessionType.PLANNED,
            status=SessionStatus.CONFIRMED,
            scheduled_at=scheduled_at,
            request_text=request_text,
            confirmed_by_user=True,
        )
        session.add(new_session)
        await session.flush()

        date_str = slot.date.strftime("%d.%m.%Y")
        time_str = slot.start_time.strftime("%H:%M")

        # Get company name
        company_name = "Unknown"
        if db_user.company_id:
            comp_result = await session.execute(select(Company).where(Company.id == db_user.company_id))
            comp = comp_result.scalar_one_or_none()
            if comp:
                company_name = comp.name

        # Notify consultant
        consultant_result = await session.execute(
            select(Consultant).where(Consultant.id == slot.consultant_id)
        )
        consultant: Consultant | None = consultant_result.scalar_one_or_none()

        await state.clear()
        await callback.message.edit_text(
            t("session_confirmed", lang, date=date_str, time=time_str),
            parse_mode="Markdown",
        )
        await touch_ui_surface(state, callback.message)

        if consultant:
            try:
                short_req = request_text[:200] + "..." if len(request_text) > 200 else request_text
                await callback.bot.send_message(
                    consultant.user_id,
                    t("c_new_session_notify", "ru",
                      date=date_str, time=time_str,
                      company=company_name, request=short_req),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to notify consultant: {e}")

        # Schedule reminders
        try:
            from bot.services.scheduler import schedule_session_reminders
            from bot.config import BOT_TOKEN
            await schedule_session_reminders(
                BOT_TOKEN, telegram_id, new_session.id,
                scheduled_at, time_str, lang
            )
        except Exception as e:
            logger.error(f"Failed to schedule reminders: {e}")


@router.callback_query(F.data == "session:cancel")
async def cb_cancel_session(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None:
        return
    await state.clear()
    lang = db_user.language
    await callback.message.edit_text(
        t("session_cancelled", lang),
        reply_markup=main_menu_keyboard(lang),
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Groups ────────────────────────────

@router.callback_query(F.data == "menu:groups")
async def cb_groups_menu(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_user(db_user):
        return
    await state.clear()
    lang = db_user.language

    async with get_session() as session:
        groups_result = await session.execute(
            select(SupportGroup).where(SupportGroup.is_active.is_(True))
        )
        groups = groups_result.scalars().all()

    if not groups:
        await callback.message.edit_text(
            t("groups_empty", lang),
            reply_markup=back_to_menu_keyboard(lang),
        )
        await touch_ui_surface(state, callback.message)
        return
    await callback.message.edit_text(
        t("groups_list", lang),
        reply_markup=groups_keyboard(groups, lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("group:"))
async def cb_group_detail(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_user(db_user):
        return
    lang = db_user.language
    group_id = int(callback.data.split(":")[1])
    telegram_id = callback.from_user.id

    async with get_session() as session:
        group_result = await session.execute(
            select(SupportGroup).where(SupportGroup.id == group_id)
        )
        group: SupportGroup | None = group_result.scalar_one_or_none()
        if group is None:
            await callback.message.edit_text(t("error_generic", lang))
            await touch_ui_surface(state, callback.message)
            return

        reg_result = await session.execute(
            select(GroupRegistration).where(
                GroupRegistration.group_id == group_id,
                GroupRegistration.user_id == telegram_id,
            )
        )
        already_joined = reg_result.scalar_one_or_none() is not None

        count_result = await session.execute(
            select(func.count()).select_from(GroupRegistration).where(GroupRegistration.group_id == group_id)
        )
        count = count_result.scalar_one()

        consultant_name = "—"
        if group.consultant_id:
            c_result = await session.execute(
                select(Consultant).where(Consultant.id == group.consultant_id)
            )
            c = c_result.scalar_one_or_none()
            if c:
                consultant_name = c.name

    name = getattr(group, f"name_{lang}", group.name_ru)
    desc = getattr(group, f"description_{lang}", group.description_ru) or "—"

    text = t(
        "group_detail", lang,
        name=name, description=desc,
        schedule=group.schedule or "—",
        consultant=consultant_name,
        count=count, max=group.max_participants,
    )
    kb = group_detail_keyboard(lang, group_id, already_joined)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("group_join:"))
async def cb_join_group(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_user(db_user):
        return
    lang = db_user.language
    group_id = int(callback.data.split(":")[1])
    telegram_id = callback.from_user.id

    async with get_session() as session:
        group_result = await session.execute(
            select(SupportGroup).where(SupportGroup.id == group_id)
        )
        group: SupportGroup | None = group_result.scalar_one_or_none()
        if group is None:
            return

        reg_result = await session.execute(
            select(GroupRegistration).where(
                GroupRegistration.group_id == group_id,
                GroupRegistration.user_id == telegram_id,
            )
        )
        if reg_result.scalar_one_or_none():
            await callback.message.edit_text(t("group_already_joined", lang))
            await touch_ui_surface(state, callback.message)
            return

        count_result = await session.execute(
            select(func.count()).select_from(GroupRegistration).where(GroupRegistration.group_id == group_id)
        )
        count = count_result.scalar_one()
        if count >= group.max_participants:
            await callback.message.edit_text(t("group_full", lang))
            await touch_ui_surface(state, callback.message)
            return

        reg = GroupRegistration(group_id=group_id, user_id=telegram_id)
        session.add(reg)

        name = getattr(group, f"name_{lang}", group.name_ru)
        company_name = "Unknown"
        if db_user.company_id:
            comp_result = await session.execute(select(Company).where(Company.id == db_user.company_id))
            comp = comp_result.scalar_one_or_none()
            if comp:
                company_name = comp.name

        await callback.message.edit_text(
            t("group_joined", lang, name=name), parse_mode="Markdown"
        )
        await touch_ui_surface(state, callback.message)

        # Notify consultant
        if group.consultant_id:
            c_result = await session.execute(
                select(Consultant).where(Consultant.id == group.consultant_id)
            )
            c = c_result.scalar_one_or_none()
            if c:
                try:
                    await callback.bot.send_message(
                        c.user_id,
                        t("group_notify_consultant", "ru", name=group.name_ru, company=company_name),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.error(f"Failed to notify group consultant: {e}")


# ──────────────────────────── My sessions ────────────────────────────

@router.callback_query(F.data == "menu:my_sessions")
async def cb_my_sessions(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_user(db_user):
        return
    await state.clear()
    lang = db_user.language
    telegram_id = callback.from_user.id

    async with get_session() as session:
        sessions_result = await session.execute(
            select(Session).where(
                Session.user_id == telegram_id,
                Session.type != SessionType.URGENT,
            ).order_by(Session.scheduled_at.desc()).limit(10)
        )
        sessions = sessions_result.scalars().all()

    if not sessions:
        await callback.message.edit_text(
            t("my_sessions_empty", lang),
            reply_markup=back_to_menu_keyboard(lang),
        )
        await touch_ui_surface(state, callback.message)
        return

    status_map = {
        "pending": t("session_status_pending", lang),
        "confirmed": t("session_status_confirmed", lang),
        "completed": t("session_status_completed", lang),
        "cancelled": t("session_status_cancelled", lang),
        "no_show": t("session_status_no_show", lang),
    }

    lines = [t("my_sessions_header", lang)]
    for s in sessions:
        if s.scheduled_at:
            date_str = s.scheduled_at.strftime("%d.%m.%Y")
            time_str = s.scheduled_at.strftime("%H:%M")
        else:
            date_str = "—"
            time_str = "—"
        status_label = status_map.get(s.status.value, s.status.value)
        lines.append(t("session_line", lang, date=date_str, time=time_str, status=status_label))

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=my_sessions_keyboard(lang, sessions),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("reschedule_from_list:"))
async def cb_reschedule_from_list(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_user(db_user):
        return
    lang = db_user.language
    session_id = int(callback.data.split(":")[1])
    telegram_id = callback.from_user.id

    async with get_session() as session:
        sess_result = await session.execute(
            select(Session).where(Session.id == session_id, Session.user_id == telegram_id)
        )
        sess = sess_result.scalar_one_or_none()
        if not sess or not sess.scheduled_at:
            await callback.message.edit_text(t("error_generic", lang), reply_markup=back_to_menu_keyboard(lang))
            await touch_ui_surface(state, callback.message)
            return

        await state.update_data(
            reschedule_session_id=session_id,
            request_text=(sess.request_text or ""),
        )

        # Show available slots (same query as booking)
        today = date.today()
        slots_result = await session.execute(
            select(ScheduleSlot)
            .join(Consultant, Consultant.id == ScheduleSlot.consultant_id)
            .where(
                ScheduleSlot.date >= today,
                ScheduleSlot.is_booked.is_(False),
                Consultant.is_active.is_(True),
            )
            .order_by(ScheduleSlot.date, ScheduleSlot.start_time)
            .limit(20)
        )
        slots = slots_result.scalars().all()

    if not slots:
        await callback.message.edit_text(t("session_no_slots", lang), reply_markup=back_to_menu_keyboard(lang))
        await touch_ui_surface(state, callback.message)
        return

    await state.set_state(SessionBookingStates.choosing_slot)
    await callback.message.edit_text(t("session_choose_slot", lang), reply_markup=slots_keyboard(slots, lang))
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Settings ────────────────────────────

@router.callback_query(F.data == "menu:settings")
async def cb_settings(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None:
        return
    await state.clear()
    lang = db_user.language
    await callback.message.edit_text(
        t("settings_menu", lang),
        reply_markup=settings_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "settings:language")
async def cb_change_language(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    await callback.message.edit_text(
        t("language_selection", "ru"),
        reply_markup=language_keyboard(),
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "settings:company")
async def cb_about_company(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None:
        return
    lang = db_user.language
    company_name = "—"
    if db_user.company_id:
        async with get_session() as session:
            result = await session.execute(
                select(Company).where(Company.id == db_user.company_id)
            )
            comp = result.scalar_one_or_none()
            if comp:
                company_name = comp.name

    await callback.message.edit_text(
        t("company_info", lang, company=company_name),
        reply_markup=settings_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "settings:delete")
async def cb_delete_account_prompt(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None or db_user.role != UserRole.USER:
        return
    lang = db_user.language
    await callback.message.edit_text(
        t("delete_account_confirm", lang),
        reply_markup=delete_confirm_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "settings:delete_confirm")
async def cb_delete_account_confirm(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None or db_user.role != UserRole.USER:
        return
    lang = db_user.language
    telegram_id = callback.from_user.id

    async with get_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user: User | None = result.scalar_one_or_none()
        if user:
            # Soft-delete to preserve foreign key integrity (sessions/feedback may reference user_id)
            user.is_deleted = True
            user.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
            user.is_blocked = False
            user.company_id = None

    await callback.message.edit_text(t("account_deleted", lang))
    # Immediately restart onboarding flow (language -> invite) so user doesn't get stuck
    sent = await callback.message.answer(
        t("language_selection", "ru"),
        reply_markup=language_keyboard(),
    )
    await touch_ui_surface(state, sent)


# ──────────────────────────── Feedback ────────────────────────────

@router.callback_query(F.data.startswith("feedback:"))
async def cb_feedback_rating(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None:
        return
    lang = db_user.language
    parts = callback.data.split(":")
    session_id = int(parts[1])
    rating = int(parts[2])
    telegram_id = callback.from_user.id

    async with get_session() as session:
        existing = await session.execute(
            select(Feedback).where(Feedback.session_id == session_id, Feedback.user_id == telegram_id)
        )
        if existing.scalar_one_or_none():
            await callback.message.edit_text(t("feedback_already_done", lang))
            await touch_ui_surface(state, callback.message)
            return

        fb = Feedback(session_id=session_id, user_id=telegram_id, rating=rating)
        session.add(fb)
        await session.flush()

        # Update session status
        sess_result = await session.execute(select(Session).where(Session.id == session_id))
        sess: Session | None = sess_result.scalar_one_or_none()
        if sess:
            sess.status = SessionStatus.COMPLETED
            sess.confirmed_by_user = True

    await state.update_data(feedback_session_id=session_id, feedback_id=None)
    await callback.message.edit_text(t("feedback_thanks", lang))
    sent = await callback.message.answer(
        t("feedback_comment_prompt", lang),
        reply_markup=feedback_comment_keyboard(lang),
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data == "feedback_comment:yes")
async def cb_feedback_comment_yes(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None:
        return
    lang = db_user.language
    await state.set_state(FeedbackStates.waiting_comment)
    await callback.message.edit_text(t("feedback_enter_comment", lang))
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "feedback_comment:no")
async def cb_feedback_comment_no(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.delete()


@router.message(FeedbackStates.waiting_comment)
async def process_feedback_comment(message: Message, state: FSMContext, db_user: User | None) -> None:
    if db_user is None:
        return
    lang = db_user.language
    comment_text = message.text or ""
    fsm_data = await state.get_data()
    session_id = fsm_data.get("feedback_session_id")

    if session_id:
        async with get_session() as session:
            fb_result = await session.execute(
                select(Feedback).where(
                    Feedback.session_id == session_id,
                    Feedback.user_id == message.from_user.id,
                )
            )
            fb: Feedback | None = fb_result.scalar_one_or_none()
            if fb:
                fb.comment = comment_text[:1000]

    await state.clear()
    sent = await message.answer(t("feedback_comment_saved", lang))
    await touch_ui_surface(state, sent)


# ──────────────────────────── Post-session buttons ────────────────────────────

@router.callback_query(F.data.startswith("session_status:"))
async def cb_session_status(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None:
        return
    lang = db_user.language
    parts = callback.data.split(":")
    status_val = parts[1]
    session_id = int(parts[2])

    if status_val == "occurred":
        async with get_session() as session:
            sess_result = await session.execute(select(Session).where(Session.id == session_id))
            sess: Session | None = sess_result.scalar_one_or_none()
            if sess:
                sess.status = SessionStatus.COMPLETED
                sess.confirmed_by_user = True

        await callback.message.edit_text(
            t("conversation_ended_user", lang),
            reply_markup=feedback_keyboard(lang, session_id),
            parse_mode="Markdown",
        )
        await touch_ui_surface(state, callback.message)
    else:
        await callback.message.edit_text(
            t("cancel_reason_prompt", lang),
            reply_markup=cancel_reason_keyboard(lang, session_id),
        )
        await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("cancel_reason:"))
async def cb_cancel_reason(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None:
        return
    lang = db_user.language
    parts = callback.data.split(":")
    session_id = int(parts[1])
    reason = parts[2]

    reason_map = {
        "user": t("cancel_reason_user", "ru"),
        "consultant": t("cancel_reason_consultant", "ru"),
        "tech": t("cancel_reason_tech", "ru"),
        "other": t("cancel_reason_other", "ru"),
    }

    company_name = "Unknown"
    async with get_session() as session:
        sess_result = await session.execute(select(Session).where(Session.id == session_id))
        sess: Session | None = sess_result.scalar_one_or_none()
        if sess:
            sess.status = SessionStatus.NO_SHOW
            sess.cancellation_reason = reason_map.get(reason, reason)
            sess.confirmed_by_user = True

            # Cancel scheduled reminders for this session
            from bot.services.scheduler import cancel_session_jobs
            cancel_session_jobs(session_id)

            user_result = await session.execute(
                select(User).where(User.telegram_id == sess.user_id)
            )
            user_obj = user_result.scalar_one_or_none()
            if user_obj and user_obj.company_id:
                comp_result = await session.execute(
                    select(Company).where(Company.id == user_obj.company_id)
                )
                comp = comp_result.scalar_one_or_none()
                if comp:
                    company_name = comp.name

        date_str = sess.scheduled_at.strftime("%d.%m.%Y %H:%M") if sess and sess.scheduled_at else "—"

    # Notify all owners
    from bot.config import OWNER_TELEGRAM_IDS
    for owner_id in OWNER_TELEGRAM_IDS:
        try:
            await callback.bot.send_message(
                owner_id,
                t("owner_notified_failed", "ru",
                  date=date_str, company=company_name, reason=reason_map.get(reason, reason)),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Failed to notify owner {owner_id}: {e}")

    await callback.message.edit_text(t("cancel_reason_saved", lang))
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Reminder responses ────────────────────────────

@router.callback_query(F.data.startswith("reminder:ok:"))
async def cb_reminder_ok(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer("👍")
    await callback.message.edit_reply_markup(reply_markup=None)
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("reminder:reschedule:"))
async def cb_reminder_reschedule(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if db_user is None:
        return
    lang = db_user.language
    await callback.message.edit_text(
        t("reschedule_contact", lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)
