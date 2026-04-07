from datetime import date, timedelta

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import t

_HOURS = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00",
          "16:00", "17:00", "18:00", "19:00", "20:00"]


def consultant_main_menu(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_c_schedule", lang), callback_data="c_menu:schedule")
    builder.button(text=t("btn_c_urgent", lang), callback_data="c_menu:urgent")
    builder.button(text=t("btn_c_sessions", lang), callback_data="c_menu:sessions")
    builder.button(text=t("btn_c_groups", lang), callback_data="c_menu:groups")
    builder.button(text=t("btn_c_stats", lang), callback_data="c_menu:stats")
    builder.button(text=t("btn_c_settings", lang), callback_data="c_menu:settings")
    builder.adjust(2)
    return builder.as_markup()


def schedule_days_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    today = date.today()
    for i in range(14):
        d = today + timedelta(days=i)
        label = d.strftime("%d.%m (%a)")
        builder.button(text=label, callback_data=f"c_day:{d.isoformat()}")
    builder.button(text=t("btn_c_schedule", lang) + " (копировать)", callback_data="c_copy_week")
    builder.button(text=t("btn_main_menu", lang), callback_data="c_menu:main")
    builder.adjust(2)
    return builder.as_markup()


def schedule_slots_keyboard(lang: str, selected_day: str, booked_times: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for hour in _HOURS:
        marker = "✅" if hour in booked_times else "⬜"
        builder.button(text=f"{marker} {hour}", callback_data=f"c_slot:{selected_day}:{hour}")
    builder.button(text="💾 Сохранить", callback_data=f"c_save:{selected_day}")
    builder.button(text=t("btn_back", lang), callback_data="c_menu:schedule")
    builder.adjust(3)
    return builder.as_markup()


def accept_urgent_keyboard(lang: str, session_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_accept_urgent", lang), callback_data=f"urgent_accept:{session_id}")
    return builder.as_markup()


def end_conversation_keyboard(lang: str, conv_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_end_conversation", lang), callback_data=f"end_conv:{conv_id}")
    return builder.as_markup()


def consultant_back_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_main_menu", lang), callback_data="c_menu:main")
    return builder.as_markup()


def consultant_settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    # Reuse existing language flow
    builder.button(text=t("btn_change_language", lang), callback_data="settings:language")
    builder.button(text=t("btn_delete_account", lang), callback_data="c_settings:delete")
    builder.button(text=t("btn_main_menu", lang), callback_data="c_menu:main")
    builder.adjust(1)
    return builder.as_markup()


def consultant_delete_confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_delete_confirm", lang), callback_data="c_settings:delete_confirm")
    builder.button(text=t("btn_cancel", lang), callback_data="c_menu:settings")
    builder.adjust(2)
    return builder.as_markup()
