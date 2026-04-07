import io
import logging
from datetime import date, datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    Company, CompanyStatus, Consultant, Feedback, GroupRegistration,
    InviteCode, InviteCodeStatus, InviteCodeType, ScheduleSlot, Session,
    SessionStatus, SupportGroup, User, UserRole, WellbeingResponse,
)
from bot.database.session import get_session
from bot.i18n import t
from bot.services.ui_surface import touch_ui_surface
from bot.keyboards.owner_kb import (
    broadcast_target_keyboard, companies_for_users_keyboard,
    companies_keyboard, company_detail_keyboard, consultant_detail_keyboard,
    consultants_for_group_keyboard, consultants_keyboard, counters_period_keyboard,
    feedback_period_keyboard, group_detail_owner_keyboard, groups_owner_keyboard,
    owner_back_keyboard, owner_main_menu, skip_keyboard,
)
from bot.services.consultant_lifecycle import restore_consultant_role
from bot.services.invite import generate_invite_codes
from bot.states import (
    OwnerBroadcastStates, OwnerCompanyStates, OwnerConsultantStates, OwnerGroupStates,
)

logger = logging.getLogger(__name__)
router = Router(name="owner")


def _require_owner(db_user: User | None) -> bool:
    return db_user is not None and db_user.role == UserRole.OWNER


# ──────────────────────────── Companies ────────────────────────────

@router.callback_query(F.data == "o_menu:companies")
async def cb_o_companies(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        await callback.answer(t("access_denied", "ru"), show_alert=True)
        return
    await callback.answer()
    lang = db_user.language

    async with get_session() as session:
        result = await session.execute(select(Company).order_by(Company.created_at.desc()))
        companies = result.scalars().all()

    await callback.message.edit_text(
        t("o_companies_list", lang),
        reply_markup=companies_keyboard(companies, lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "o_company:new")
async def cb_o_new_company(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    await state.set_state(OwnerCompanyStates.entering_name)
    await callback.message.edit_text(t("o_company_enter_name", lang))
    await touch_ui_surface(state, callback.message)


@router.message(OwnerCompanyStates.entering_name)
async def o_company_name(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(company_name=message.text.strip())
    await state.set_state(OwnerCompanyStates.entering_limit)
    await message.answer(t("o_company_enter_limit", lang))


@router.message(OwnerCompanyStates.entering_limit)
async def o_company_limit(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    try:
        limit = int(message.text.strip())
        if limit <= 0:
            raise ValueError
    except ValueError:
        await message.answer(t("o_company_invalid_limit", lang))
        return

    await state.update_data(company_limit=limit)
    await state.set_state(OwnerCompanyStates.entering_contract_end)
    sent = await message.answer(
        t("o_company_enter_contract_end", lang), reply_markup=skip_keyboard(lang)
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data == "skip", OwnerCompanyStates.entering_contract_end)
async def o_company_skip_date(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    fsm_data = await state.get_data()
    await _create_company(callback.message, state, db_user, fsm_data, None)


@router.message(OwnerCompanyStates.entering_contract_end)
async def o_company_contract_date(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    date_str = message.text.strip()
    try:
        contract_end = date.fromisoformat(date_str)
    except ValueError:
        await message.answer(t("o_company_invalid_date", lang))
        return

    fsm_data = await state.get_data()
    await _create_company(message, state, db_user, fsm_data, contract_end)


async def _create_company(
    msg: Message, state: FSMContext, db_user: User | None,
    fsm_data: dict, contract_end: date | None
) -> None:
    lang = db_user.language
    name = fsm_data.get("company_name", "Company")
    limit = fsm_data.get("company_limit", 10)

    company_id: int | None = None
    async with get_session() as session:
        company = Company(
            name=name,
            max_users=limit,
            contract_start=date.today(),
            contract_end=contract_end,
        )
        session.add(company)
        await session.flush()
        company_id = company.id

    await state.clear()
    sent = await msg.answer(
        t("o_company_created", lang, name=name),
        reply_markup=company_detail_keyboard(lang, company_id, is_active=True),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data.startswith("o_company:"))
async def cb_o_company_detail(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    company_id_str = callback.data.split(":")[1]
    if company_id_str == "new":
        return  # handled above
    company_id = int(company_id_str)

    async with get_session() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company: Company | None = result.scalar_one_or_none()
        if company is None:
            return

        users_count = (await session.execute(
            select(func.count()).select_from(User).where(User.company_id == company_id, User.is_blocked.is_(False))
        )).scalar_one()

    contract_end_str = company.contract_end.isoformat() if company.contract_end else "—"
    text = t("o_company_detail", lang,
              name=company.name,
              max_users=company.max_users,
              active_users=users_count,
              contract_end=contract_end_str,
              status=company.status.value)
    kb = company_detail_keyboard(lang, company_id, company.status == CompanyStatus.ACTIVE)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_gen_codes:"))
async def cb_o_gen_codes(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    company_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company: Company | None = result.scalar_one_or_none()
        if company is None:
            return

        # Count existing active codes
        existing_count = (await session.execute(
            select(func.count()).select_from(InviteCode).where(
                InviteCode.company_id == company_id,
                InviteCode.status == InviteCodeStatus.ACTIVE,
            )
        )).scalar_one()

        # Count active users
        active_users = (await session.execute(
            select(func.count()).select_from(User).where(
                User.company_id == company_id, User.is_blocked.is_(False)
            )
        )).scalar_one()

        to_generate = company.max_users - active_users - existing_count
        if to_generate <= 0:
            lang = db_user.language
            await callback.answer(t("o_limit_already_issued", lang), show_alert=True)
            return

        raw_codes = await generate_invite_codes(session, company, to_generate)

    # Generate TXT file with codes
    bot_username = (await callback.bot.get_me()).username
    lines = [f"=== Инвайт-коды для {company.name} ===", ""]
    for code in raw_codes:
        deep_link = f"https://t.me/{bot_username}?start={code}"
        lines.append(f"{code}")
        lines.append(f"Deep-link: {deep_link}")
        lines.append("")

    file_content = "\n".join(lines).encode("utf-8")
    file = BufferedInputFile(file_content, filename=f"codes_{company.name}.txt")
    await callback.message.answer_document(
        file,
        caption=t("o_codes_generated", lang, count=to_generate),
    )


@router.callback_query(F.data.startswith("o_company_stats:"))
async def cb_o_company_stats(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    company_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company: Company | None = result.scalar_one_or_none()
        if company is None:
            return

        users_count = (await session.execute(
            select(func.count()).select_from(User).where(User.company_id == company_id, User.is_blocked.is_(False))
        )).scalar_one()

        sessions_count = (await session.execute(
            select(func.count()).select_from(Session).where(
                Session.status == SessionStatus.COMPLETED,
                Session.user_id.in_(
                    select(User.telegram_id).where(User.company_id == company_id)
                ),
            )
        )).scalar_one()

        avg_feedback = (await session.execute(
            select(func.avg(Feedback.rating)).where(
                Feedback.user_id.in_(
                    select(User.telegram_id).where(User.company_id == company_id)
                )
            )
        )).scalar_one()

    avg_str = f"{avg_feedback:.1f}" if avg_feedback else "—"
    await callback.message.edit_text(
        t("o_company_stats", lang,
          name=company.name, users=users_count,
          sessions=sessions_count, avg_feedback=avg_str),
        reply_markup=owner_back_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_deactivate:"))
async def cb_o_deactivate(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    company_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company: Company | None = result.scalar_one_or_none()
        if company:
            company.status = CompanyStatus.INACTIVE
            # Revoke all active codes
            codes_result = await session.execute(
                select(InviteCode).where(
                    InviteCode.company_id == company_id,
                    InviteCode.status == InviteCodeStatus.ACTIVE,
                )
            )
            for code in codes_result.scalars().all():
                code.status = InviteCodeStatus.REVOKED

    await callback.message.edit_text(t("o_company_deactivated", lang), reply_markup=owner_back_keyboard(lang))
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_activate:"))
async def cb_o_activate(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    company_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company: Company | None = result.scalar_one_or_none()
        if company:
            company.status = CompanyStatus.ACTIVE

    await callback.message.edit_text(t("o_company_activated", lang), reply_markup=owner_back_keyboard(lang))
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Users ────────────────────────────

@router.callback_query(F.data == "o_menu:users")
async def cb_o_users(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language

    async with get_session() as session:
        result = await session.execute(select(Company).order_by(Company.name))
        companies = result.scalars().all()

    await callback.message.edit_text(
        t("o_users_list", lang),
        reply_markup=companies_for_users_keyboard(companies, lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_users_company:"))
async def cb_o_users_in_company(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    company_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(Company).where(Company.id == company_id))
        company: Company | None = result.scalar_one_or_none()

        users_result = await session.execute(
            select(User).where(
                User.company_id == company_id,
                User.role == UserRole.USER,
            ).limit(50)
        )
        users = users_result.scalars().all()

    if not users:
        await callback.message.edit_text(
            t("o_users_in_company", lang, company=company.name if company else "?", count=0),
            reply_markup=owner_back_keyboard(lang),
        )
        await touch_ui_surface(state, callback.message)
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    lines = [t("o_users_in_company", lang,
                company=company.name if company else "?", count=len(users))]
    for u in users:
        status = "🚫" if u.is_blocked else "✅"
        action = "unblock" if u.is_blocked else "block"
        builder.button(
            text=f"{status} ID:{u.telegram_id}",
            callback_data=f"o_user_{action}:{u.telegram_id}"
        )
    builder.button(text=t("btn_back", lang), callback_data="o_menu:users")
    builder.adjust(1)

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_user_block:"))
async def cb_o_block_user(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        await callback.answer()
        return
    lang = db_user.language
    user_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        target: User | None = result.scalar_one_or_none()
        if target:
            target.is_blocked = True

    await callback.answer(t("o_user_blocked", lang), show_alert=True)


@router.callback_query(F.data.startswith("o_user_unblock:"))
async def cb_o_unblock_user(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        await callback.answer()
        return
    lang = db_user.language
    user_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_id))
        target: User | None = result.scalar_one_or_none()
        if target:
            target.is_blocked = False

    await callback.answer(t("o_user_unblocked", lang), show_alert=True)


# ──────────────────────────── Consultants ────────────────────────────

@router.callback_query(F.data == "o_menu:consultants")
async def cb_o_consultants(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language

    async with get_session() as session:
        result = await session.execute(select(Consultant).order_by(Consultant.name))
        consultants = result.scalars().all()

    await callback.message.edit_text(
        t("o_consultants_list", lang),
        reply_markup=consultants_keyboard(consultants, lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "o_consultant:new")
async def cb_o_add_consultant(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    await state.set_state(OwnerConsultantStates.entering_telegram_id)
    await callback.message.edit_text(t("o_consultant_enter_tid", lang))
    await touch_ui_surface(state, callback.message)


@router.message(OwnerConsultantStates.entering_telegram_id)
async def o_consultant_tid(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    try:
        tid = int(message.text.strip())
    except ValueError:
        await message.answer(t("o_consultant_invalid_tid", lang))
        return

    async with get_session() as session:
        result = await session.execute(select(Consultant).where(Consultant.user_id == tid))
        existing = result.scalar_one_or_none()
        if existing and existing.is_active:
            await message.answer(t("o_consultant_exists", lang))
            return
        if existing and not existing.is_active:
            # Allow re-activating a previously removed consultant
            await state.update_data(existing_consultant_id=existing.id)

    await state.update_data(consultant_tid=tid)
    await state.set_state(OwnerConsultantStates.entering_name)
    await message.answer(t("o_consultant_enter_name", lang))


@router.message(OwnerConsultantStates.entering_name)
async def o_consultant_name(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(consultant_name=message.text.strip())
    await state.set_state(OwnerConsultantStates.entering_specialization)
    sent = await message.answer(
        t("o_consultant_enter_spec", lang), reply_markup=skip_keyboard(lang)
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data == "skip", OwnerConsultantStates.entering_specialization)
async def o_consultant_skip_spec(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    await _create_consultant(callback.message, state, db_user, None)


@router.message(OwnerConsultantStates.entering_specialization)
async def o_consultant_spec(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    if not message.text:
        return
    await _create_consultant(message, state, db_user, message.text.strip())


async def _create_consultant(msg: Message, state: FSMContext, db_user: User | None, spec: str | None) -> None:
    lang = db_user.language
    fsm_data = await state.get_data()
    tid = fsm_data.get("consultant_tid")
    name = fsm_data.get("consultant_name", "Consultant")
    existing_consultant_id = fsm_data.get("existing_consultant_id")

    async with get_session() as session:
        # Ensure user record exists (consultant may not have registered yet)
        user_result = await session.execute(select(User).where(User.telegram_id == tid))
        user_obj = user_result.scalar_one_or_none()
        if user_obj is None:
            user_obj = User(telegram_id=tid, role=UserRole.CONSULTANT, language="ru")
            session.add(user_obj)
        else:
            user_obj.role = UserRole.CONSULTANT

        if existing_consultant_id:
            c_result = await session.execute(select(Consultant).where(Consultant.id == existing_consultant_id))
            consultant = c_result.scalar_one_or_none()
            if consultant:
                consultant.is_active = True
                consultant.user_id = tid
                consultant.name = name
                consultant.specialization = spec
        else:
            consultant = Consultant(user_id=tid, name=name, specialization=spec)
            session.add(consultant)

    bot_username = (await msg.bot.get_me()).username
    # Consultant is already registered via their Telegram ID — they just need to /start the bot
    invite_link = f"https://t.me/{bot_username}"

    await state.clear()
    # Avoid Markdown issues with underscores in bot username/links.
    sent = await msg.answer(t("o_consultant_added", lang, name=name, link=invite_link))
    await touch_ui_surface(state, sent)


@router.callback_query(F.data.startswith("o_consultant_detail:"))
async def cb_o_consultant_detail(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    consultant_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(Consultant).where(Consultant.id == consultant_id))
        c: Consultant | None = result.scalar_one_or_none()
        if c is None:
            return

        sessions_count = (await session.execute(
            select(func.count()).select_from(Session).where(
                Session.consultant_id == consultant_id,
                Session.status == SessionStatus.COMPLETED,
            )
        )).scalar_one()

    text = f"🧠 *{c.name}*\n\n"
    if c.specialization:
        text += f"🔬 Специализация: {c.specialization}\n"
    text += f"📊 Сессий: {sessions_count}"

    await callback.message.edit_text(
        text,
        reply_markup=consultant_detail_keyboard(lang, consultant_id, is_active=c.is_active),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_consultant_remove:"))
async def cb_o_consultant_remove(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    consultant_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(Consultant).where(Consultant.id == consultant_id))
        c: Consultant | None = result.scalar_one_or_none()
        if c:
            c.is_active = False
            # Change role back to user
            user_result = await session.execute(select(User).where(User.telegram_id == c.user_id))
            user_obj = user_result.scalar_one_or_none()
            if user_obj:
                user_obj.role = UserRole.USER

    await callback.message.edit_text(
        t("o_consultant_removed", lang),
        reply_markup=owner_back_keyboard(lang),
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_consultant_restore:"))
async def cb_o_consultant_restore(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    consultant_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(Consultant).where(Consultant.id == consultant_id))
        c: Consultant | None = result.scalar_one_or_none()
        if c:
            user_result = await session.execute(select(User).where(User.telegram_id == c.user_id))
            user_obj = user_result.scalar_one_or_none()
            restore_consultant_role(c, user_obj)

    await callback.message.edit_text(
        t("o_consultant_restored", lang),
        reply_markup=owner_back_keyboard(lang),
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Groups ────────────────────────────

@router.callback_query(F.data == "o_menu:groups")
async def cb_o_groups(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language

    async with get_session() as session:
        result = await session.execute(
            select(SupportGroup).where(SupportGroup.is_active.is_(True))
        )
        groups = result.scalars().all()

    await callback.message.edit_text(
        t("o_groups_list", lang),
        reply_markup=groups_owner_keyboard(groups, lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data == "o_group:new")
async def cb_o_new_group(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    await state.set_state(OwnerGroupStates.entering_name_ru)
    await callback.message.edit_text(t("o_group_enter_name_ru", lang))
    await touch_ui_surface(state, callback.message)


@router.message(OwnerGroupStates.entering_name_ru)
async def o_group_name_ru(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(group_name_ru=message.text.strip())
    await state.set_state(OwnerGroupStates.entering_name_en)
    await message.answer(t("o_group_enter_name_en", lang))


@router.message(OwnerGroupStates.entering_name_en)
async def o_group_name_en(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(group_name_en=message.text.strip())
    await state.set_state(OwnerGroupStates.entering_name_ua)
    await message.answer(t("o_group_enter_name_ua", lang))


@router.message(OwnerGroupStates.entering_name_ua)
async def o_group_name_ua(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(group_name_ua=message.text.strip())
    await state.set_state(OwnerGroupStates.entering_desc_ru)
    sent = await message.answer(
        t("o_group_enter_desc_ru", lang), reply_markup=skip_keyboard(lang)
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data == "skip", OwnerGroupStates.entering_desc_ru)
async def o_group_skip_desc_ru(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    await state.update_data(group_desc_ru=None)
    lang = db_user.language
    await state.set_state(OwnerGroupStates.entering_desc_en)
    await callback.message.edit_text(t("o_group_enter_desc_en", lang), reply_markup=skip_keyboard(lang))
    await touch_ui_surface(state, callback.message)


@router.message(OwnerGroupStates.entering_desc_ru)
async def o_group_desc_ru(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(group_desc_ru=message.text.strip())
    await state.set_state(OwnerGroupStates.entering_desc_en)
    sent = await message.answer(
        t("o_group_enter_desc_en", lang), reply_markup=skip_keyboard(lang)
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data == "skip", OwnerGroupStates.entering_desc_en)
async def o_group_skip_desc_en(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    await state.update_data(group_desc_en=None)
    lang = db_user.language
    await state.set_state(OwnerGroupStates.entering_desc_ua)
    await callback.message.edit_text(t("o_group_enter_desc_ua", lang), reply_markup=skip_keyboard(lang))
    await touch_ui_surface(state, callback.message)


@router.message(OwnerGroupStates.entering_desc_en)
async def o_group_desc_en(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(group_desc_en=message.text.strip())
    await state.set_state(OwnerGroupStates.entering_desc_ua)
    sent = await message.answer(
        t("o_group_enter_desc_ua", lang), reply_markup=skip_keyboard(lang)
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data == "skip", OwnerGroupStates.entering_desc_ua)
async def o_group_skip_desc_ua(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    await state.update_data(group_desc_ua=None)
    lang = db_user.language
    await state.set_state(OwnerGroupStates.choosing_consultant)
    await _show_consultant_choice(callback.message, lang, state)


@router.message(OwnerGroupStates.entering_desc_ua)
async def o_group_desc_ua(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(group_desc_ua=message.text.strip())
    await state.set_state(OwnerGroupStates.choosing_consultant)
    await _show_consultant_choice(message, lang, state)


async def _show_consultant_choice(msg: Message, lang: str, state: FSMContext) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(Consultant).where(Consultant.is_active.is_(True))
        )
        consultants = result.scalars().all()
    sent = await msg.answer(
        t("o_group_choose_consultant", lang),
        reply_markup=consultants_for_group_keyboard(consultants, lang),
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data.startswith("o_group_consultant:"))
async def o_group_consultant_chosen(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    val = callback.data.split(":")[1]
    consultant_id = None if val == "none" else int(val)
    await state.update_data(group_consultant_id=consultant_id)
    await state.set_state(OwnerGroupStates.entering_max_participants)
    await callback.message.edit_text(t("o_group_enter_max", lang))
    await touch_ui_surface(state, callback.message)


@router.message(OwnerGroupStates.entering_max_participants)
async def o_group_max(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    try:
        max_p = int(message.text.strip())
    except ValueError:
        await message.answer(t("o_company_invalid_limit", lang))
        return
    await state.update_data(group_max=max_p)
    await state.set_state(OwnerGroupStates.entering_schedule)
    sent = await message.answer(
        t("o_group_enter_schedule", lang), reply_markup=skip_keyboard(lang)
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data == "skip", OwnerGroupStates.entering_schedule)
async def o_group_skip_schedule(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    await _save_group(callback.message, state, db_user, None)


@router.message(OwnerGroupStates.entering_schedule)
async def o_group_schedule(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    if not message.text:
        return
    await _save_group(message, state, db_user, message.text.strip())


async def _save_group(msg: Message, state: FSMContext, db_user: User | None, schedule: str | None) -> None:
    lang = db_user.language
    fsm_data = await state.get_data()

    async with get_session() as session:
        group = SupportGroup(
            name_ru=fsm_data.get("group_name_ru", "Группа"),
            name_en=fsm_data.get("group_name_en", "Group"),
            name_ua=fsm_data.get("group_name_ua", "Група"),
            description_ru=fsm_data.get("group_desc_ru"),
            description_en=fsm_data.get("group_desc_en"),
            description_ua=fsm_data.get("group_desc_ua"),
            consultant_id=fsm_data.get("group_consultant_id"),
            max_participants=fsm_data.get("group_max", 20),
            schedule=schedule,
        )
        session.add(group)

    await state.clear()
    name = fsm_data.get("group_name_ru", "Группа")
    sent = await msg.answer(t("o_group_created", lang, name=name), parse_mode="Markdown")
    await touch_ui_surface(state, sent)


@router.callback_query(F.data.startswith("o_group_detail:"))
async def cb_o_group_detail(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    group_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(SupportGroup).where(SupportGroup.id == group_id))
        group: SupportGroup | None = result.scalar_one_or_none()
        if group is None:
            return

        count = (await session.execute(
            select(func.count()).select_from(GroupRegistration).where(GroupRegistration.group_id == group_id)
        )).scalar_one()

    name = getattr(group, f"name_{lang}", group.name_ru)
    await callback.message.edit_text(
        t("o_group_line", lang, name=name, count=count),
        reply_markup=group_detail_owner_keyboard(lang, group_id),
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_group_delete:"))
async def cb_o_group_delete(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    group_id = int(callback.data.split(":")[1])

    async with get_session() as session:
        result = await session.execute(select(SupportGroup).where(SupportGroup.id == group_id))
        group: SupportGroup | None = result.scalar_one_or_none()
        if group is None:
            return

        group.is_active = False

        # Get all registrations and notify users
        regs_result = await session.execute(
            select(GroupRegistration).where(GroupRegistration.group_id == group_id)
        )
        regs = regs_result.scalars().all()

        for reg in regs:
            user_result = await session.execute(select(User).where(User.telegram_id == reg.user_id))
            user_obj = user_result.scalar_one_or_none()
            user_lang = user_obj.language if user_obj else "ru"
            name = getattr(group, f"name_{user_lang}", group.name_ru)
            try:
                await callback.bot.send_message(
                    reg.user_id,
                    t("group_deleted_notify", user_lang, name=name),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to notify user {reg.user_id} about group deletion: {e}")

    await callback.message.edit_text(
        t("o_group_deleted", lang),
        reply_markup=owner_back_keyboard(lang),
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Mental Feedback ────────────────────────────

@router.callback_query(F.data == "o_menu:feedback")
async def cb_o_feedback(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    await callback.message.edit_text(
        t("o_feedback_choose_period", lang),
        reply_markup=feedback_period_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_feedback:"))
async def cb_o_feedback_period(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    period = callback.data.split(":")[1]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "week":
        from_dt = now - timedelta(days=7)
        period_label = t("btn_period_week", lang)
    elif period == "month":
        from_dt = now - timedelta(days=30)
        period_label = t("btn_period_month", lang)
    else:
        from_dt = datetime(2000, 1, 1)
        period_label = t("btn_period_all", lang)

    async with get_session() as session:
        fb_result = await session.execute(
            select(Feedback).where(Feedback.created_at >= from_dt).order_by(Feedback.created_at)
        )
        feedbacks = fb_result.scalars().all()

    if not feedbacks:
        await callback.message.edit_text(
            t("o_feedback_no_data", lang),
            reply_markup=feedback_period_keyboard(lang),
        )
        await touch_ui_surface(state, callback.message)
        return

    ratings = [f.rating for f in feedbacks]
    avg = sum(ratings) / len(ratings)
    median = sorted(ratings)[len(ratings) // 2]

    lines = [
        "--- Mental Feedback Report ---",
        f"Period: {period_label}",
        f"Total ratings: {len(ratings)} | Average: {avg:.1f} | Median: {median}",
        "---",
    ]
    for f in feedbacks:
        lines.append(f"{f.created_at.strftime('%Y-%m-%d %H:%M:%S')}:{f.rating}")

    file_content = "\n".join(lines).encode("utf-8")
    file = BufferedInputFile(file_content, filename=f"feedback_{period}.txt")
    await callback.message.answer_document(
        file,
        caption=t("o_feedback_file_caption", lang, period=period_label),
    )


# ──────────────────────────── Session counters ────────────────────────────

@router.callback_query(F.data == "o_menu:counters")
async def cb_o_counters(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    await callback.message.edit_text(
        t("o_counters_choose", lang),
        reply_markup=counters_period_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


@router.callback_query(F.data.startswith("o_counters:"))
async def cb_o_counters_period(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    parts = callback.data.split(":")
    period = parts[1]
    mode = parts[2]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if period == "week":
        from_dt = now - timedelta(days=7)
        period_label = t("btn_period_week", lang)
    elif period == "month":
        from_dt = now - timedelta(days=30)
        period_label = t("btn_period_month", lang)
    else:
        from_dt = datetime(2000, 1, 1)
        period_label = t("btn_period_all", lang)

    async with get_session() as session:
        if mode == "by_consultant":
            consultants_result = await session.execute(select(Consultant))
            consultants = consultants_result.scalars().all()
            lines = []
            for c in consultants:
                count = (await session.execute(
                    select(func.count()).select_from(Session).where(
                        Session.consultant_id == c.id,
                        Session.status == SessionStatus.COMPLETED,
                        Session.scheduled_at >= from_dt,
                    )
                )).scalar_one()
                lines.append(t("o_counters_line_consultant", lang, name=c.name, count=count))
            data = "\n".join(lines) if lines else "—"
        else:
            total = (await session.execute(
                select(func.count()).select_from(Session).where(
                    Session.status == SessionStatus.COMPLETED,
                    Session.scheduled_at >= from_dt,
                )
            )).scalar_one()
            data = t("o_counters_total", lang, count=total)

    await callback.message.edit_text(
        t("o_counters_result", lang, period=period_label, data=data),
        reply_markup=counters_period_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Failed sessions ────────────────────────────

@router.callback_query(F.data == "o_menu:failed")
async def cb_o_failed(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language

    async with get_session() as session:
        result = await session.execute(
            select(Session).where(
                Session.status == SessionStatus.NO_SHOW
            ).order_by(Session.scheduled_at.desc()).limit(30)
        )
        failed = result.scalars().all()

    if not failed:
        await callback.message.edit_text(
            t("o_failed_empty", lang),
            reply_markup=owner_back_keyboard(lang),
        )
        await touch_ui_surface(state, callback.message)
        return

    # Batch-load users and companies to avoid N+1 queries
    user_ids = [s.user_id for s in failed]
    async with get_session() as session2:
        users_result = await session2.execute(
            select(User).where(User.telegram_id.in_(user_ids))
        )
        users_map = {u.telegram_id: u for u in users_result.scalars().all()}

        company_ids = {u.company_id for u in users_map.values() if u.company_id}
        companies_map: dict[int, Company] = {}
        if company_ids:
            comps_result = await session2.execute(
                select(Company).where(Company.id.in_(company_ids))
            )
            companies_map = {c.id: c for c in comps_result.scalars().all()}

    lines = [t("o_failed_sessions_header", lang)]
    for s in failed:
        date_str = s.scheduled_at.strftime("%d.%m.%Y %H:%M") if s.scheduled_at else "—"
        company_name = "Unknown"
        user_obj = users_map.get(s.user_id)
        if user_obj and user_obj.company_id:
            comp = companies_map.get(user_obj.company_id)
            if comp:
                company_name = comp.name
        lines.append(t("o_failed_line", lang,
                       date=date_str, company=company_name,
                       reason=s.cancellation_reason or "—"))

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=owner_back_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── Broadcast ────────────────────────────

@router.callback_query(F.data == "o_menu:broadcast")
async def cb_o_broadcast(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    await state.set_state(OwnerBroadcastStates.entering_text)
    await callback.message.edit_text(t("broadcast_enter_text", lang))
    await touch_ui_surface(state, callback.message)


@router.message(OwnerBroadcastStates.entering_text)
async def o_broadcast_text(message: Message, state: FSMContext, db_user: User | None) -> None:
    if not _require_owner(db_user):
        return
    lang = db_user.language
    if not message.text:
        return
    await state.update_data(broadcast_text=message.text)
    await state.set_state(OwnerBroadcastStates.choosing_target)
    sent = await message.answer(
        t("broadcast_choose_target", lang),
        reply_markup=broadcast_target_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, sent)


@router.callback_query(F.data.startswith("broadcast:"), OwnerBroadcastStates.choosing_target)
async def o_broadcast_send(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    target = callback.data.split(":")[1]
    fsm_data = await state.get_data()
    text = fsm_data.get("broadcast_text", "")

    async with get_session() as session:
        if target == "all":
            users_result = await session.execute(
                select(User).where(User.role == UserRole.USER, User.is_blocked.is_(False))
            )
            recipients = [u.telegram_id for u in users_result.scalars().all()]
        elif target == "consultants":
            consultants_result = await session.execute(
                select(Consultant).where(Consultant.is_active.is_(True))
            )
            recipients = [c.user_id for c in consultants_result.scalars().all()]
        else:
            recipients = []

    sent = 0
    for uid in recipients:
        try:
            await callback.bot.send_message(uid, text, parse_mode="Markdown")
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for user {uid}: {e}")

    await state.clear()
    await callback.message.edit_text(t("broadcast_sent", lang, count=sent))
    await touch_ui_surface(state, callback.message)


# ──────────────────────────── WHO-5 stats ────────────────────────────

@router.callback_query(F.data == "o_menu:wellbeing")
async def cb_o_wellbeing(callback: CallbackQuery, state: FSMContext, db_user: User | None) -> None:
    await callback.answer()
    if not _require_owner(db_user):
        return
    lang = db_user.language
    async with get_session() as session:
        n = await session.scalar(select(func.count()).select_from(WellbeingResponse))
        avg = await session.scalar(select(func.avg(WellbeingResponse.score_raw)))
    if not n:
        await callback.message.edit_text(
            t("o_wellbeing_empty", lang),
            reply_markup=owner_back_keyboard(lang),
            parse_mode="Markdown",
        )
        await touch_ui_surface(state, callback.message)
        return
    await callback.message.edit_text(
        t("o_wellbeing_stats", lang, count=int(n), avg=float(avg or 0)),
        reply_markup=owner_back_keyboard(lang),
        parse_mode="Markdown",
    )
    await touch_ui_surface(state, callback.message)
