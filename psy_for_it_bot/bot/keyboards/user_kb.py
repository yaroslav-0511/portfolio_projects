from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import t


def language_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru")
    builder.button(text="🇬🇧 English", callback_data="lang:en")
    builder.button(text="🇺🇦 Українська", callback_data="lang:ua")
    builder.adjust(3)
    return builder.as_markup()


def enter_code_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("enter_invite_code", lang), callback_data="enter_code")
    return builder.as_markup()


def main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_emergency", lang), callback_data="menu:emergency")
    builder.button(text=t("btn_session", lang), callback_data="menu:session")
    builder.button(text=t("btn_groups", lang), callback_data="menu:groups")
    builder.button(text=t("btn_self_help", lang), callback_data="menu:self_help")
    builder.button(text=t("btn_wellbeing", lang), callback_data="menu:wellbeing")
    builder.button(text=t("btn_my_sessions", lang), callback_data="menu:my_sessions")
    builder.button(text=t("btn_settings", lang), callback_data="menu:settings")
    builder.adjust(1, 1, 1, 1, 1, 2)
    return builder.as_markup()


def back_to_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_main_menu", lang), callback_data="menu:main")
    return builder.as_markup()


def session_confirm_keyboard(lang: str, slot_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_yes", lang), callback_data=f"session:confirm:{slot_id}")
    builder.button(text=t("btn_no_cancel", lang), callback_data="session:cancel")
    builder.adjust(2)
    return builder.as_markup()


def slots_keyboard(slots: list, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        label = f"📅 {slot.date.strftime('%d.%m')} {slot.start_time.strftime('%H:%M')}"
        builder.button(text=label, callback_data=f"slot:{slot.id}")
    builder.button(text=t("btn_main_menu", lang), callback_data="menu:main")
    builder.adjust(2)
    return builder.as_markup()


def groups_keyboard(groups: list, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group in groups:
        name = getattr(group, f"name_{lang}", group.name_ru)
        builder.button(text=name, callback_data=f"group:{group.id}")
    builder.button(text=t("btn_main_menu", lang), callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def group_detail_keyboard(lang: str, group_id: int, already_joined: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not already_joined:
        builder.button(text=t("btn_join_group", lang), callback_data=f"group_join:{group_id}")
    builder.button(text=t("btn_back", lang), callback_data="menu:groups")
    builder.adjust(1)
    return builder.as_markup()


def feedback_keyboard(lang: str, session_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 11):
        builder.button(text=str(i), callback_data=f"feedback:{session_id}:{i}")
    builder.adjust(5, 5)
    return builder.as_markup()


def feedback_comment_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_feedback_comment_yes", lang), callback_data="feedback_comment:yes")
    builder.button(text=t("btn_feedback_comment_no", lang), callback_data="feedback_comment:no")
    builder.adjust(2)
    return builder.as_markup()


def post_session_keyboard(lang: str, session_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t("btn_session_occurred", lang),
        callback_data=f"session_status:occurred:{session_id}"
    )
    builder.button(
        text=t("btn_session_not_occurred", lang),
        callback_data=f"session_status:not_occurred:{session_id}"
    )
    builder.adjust(1)
    return builder.as_markup()


def cancel_reason_keyboard(lang: str, session_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_reason_user", lang), callback_data=f"cancel_reason:{session_id}:user")
    builder.button(text=t("btn_reason_consultant", lang), callback_data=f"cancel_reason:{session_id}:consultant")
    builder.button(text=t("btn_reason_tech", lang), callback_data=f"cancel_reason:{session_id}:tech")
    builder.button(text=t("btn_reason_other", lang), callback_data=f"cancel_reason:{session_id}:other")
    builder.adjust(1)
    return builder.as_markup()


def reminder_keyboard(lang: str, session_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_reminder_ok", lang), callback_data=f"reminder:ok:{session_id}")
    builder.button(text=t("btn_reminder_reschedule", lang), callback_data=f"reminder:reschedule:{session_id}")
    builder.adjust(2)
    return builder.as_markup()


def my_sessions_keyboard(lang: str, sessions: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Provide a reschedule button for upcoming confirmed sessions
    for s in sessions:
        if getattr(s, "scheduled_at", None) and getattr(s, "status", None) and s.status.value == "confirmed":
            label = f"📅 {s.scheduled_at.strftime('%d.%m %H:%M')} — {t('btn_reminder_reschedule', lang)}"
            builder.button(text=label, callback_data=f"reschedule_from_list:{s.id}")
    builder.button(text=t("btn_main_menu", lang), callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_change_language", lang), callback_data="settings:language")
    builder.button(text=t("btn_about_company", lang), callback_data="settings:company")
    builder.button(text=t("btn_delete_account", lang), callback_data="settings:delete")
    builder.button(text=t("btn_main_menu", lang), callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_delete_confirm", lang), callback_data="settings:delete_confirm")
    builder.button(text=t("btn_cancel", lang), callback_data="menu:settings")
    builder.adjust(2)
    return builder.as_markup()


def who5_start_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_who5_start", lang), callback_data="who5:start")
    builder.button(text=t("btn_main_menu", lang), callback_data="menu:main")
    builder.adjust(1)
    return builder.as_markup()


def who5_scale_keyboard(lang: str, session_id: str, q_index: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(6):
        builder.button(
            text=str(i),
            callback_data=f"who5:v:{session_id}:{q_index}:{i}",
        )
    builder.button(
        text=t("btn_cancel", lang),
        callback_data=f"who5:cancel:{session_id}",
    )
    builder.adjust(6, 1)
    return builder.as_markup()


def self_help_nav_keyboard(lang: str, page: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text=t("btn_self_help_prev", lang), callback_data=f"self_help:page:{page - 1}")
    if page < total - 1:
        builder.button(text=t("btn_self_help_next", lang), callback_data=f"self_help:page:{page + 1}")
    builder.button(text=t("btn_main_menu", lang), callback_data="menu:main")
    builder.adjust(2)
    return builder.as_markup()
