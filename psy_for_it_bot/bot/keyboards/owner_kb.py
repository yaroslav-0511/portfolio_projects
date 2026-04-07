from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import t


def owner_main_menu(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_o_companies", lang), callback_data="o_menu:companies")
    builder.button(text=t("btn_o_users", lang), callback_data="o_menu:users")
    builder.button(text=t("btn_o_consultants", lang), callback_data="o_menu:consultants")
    builder.button(text=t("btn_o_groups", lang), callback_data="o_menu:groups")
    builder.button(text=t("btn_o_feedback", lang), callback_data="o_menu:feedback")
    builder.button(text=t("btn_o_counters", lang), callback_data="o_menu:counters")
    builder.button(text=t("btn_o_failed", lang), callback_data="o_menu:failed")
    builder.button(text=t("btn_o_broadcast", lang), callback_data="o_menu:broadcast")
    builder.button(text=t("btn_o_wellbeing", lang), callback_data="o_menu:wellbeing")
    builder.adjust(2)
    return builder.as_markup()


def companies_keyboard(companies: list, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for company in companies:
        status_icon = "✅" if company.status.value == "active" else "⛔"
        builder.button(
            text=f"{status_icon} {company.name}",
            callback_data=f"o_company:{company.id}"
        )
    builder.button(text=t("btn_o_new_company", lang), callback_data="o_company:new")
    builder.button(text=t("btn_main_menu", lang), callback_data="o_menu:main")
    builder.adjust(1)
    return builder.as_markup()


def company_detail_keyboard(lang: str, company_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_o_gen_codes", lang), callback_data=f"o_gen_codes:{company_id}")
    builder.button(text=t("btn_o_view_stats", lang), callback_data=f"o_company_stats:{company_id}")
    if is_active:
        builder.button(text=t("btn_o_deactivate", lang), callback_data=f"o_deactivate:{company_id}")
    else:
        builder.button(text=t("btn_o_activate", lang), callback_data=f"o_activate:{company_id}")
    builder.button(text=t("btn_back", lang), callback_data="o_menu:companies")
    builder.adjust(1)
    return builder.as_markup()


def skip_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_skip", lang), callback_data="skip")
    return builder.as_markup()


def companies_for_users_keyboard(companies: list, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for company in companies:
        builder.button(text=company.name, callback_data=f"o_users_company:{company.id}")
    builder.button(text=t("btn_main_menu", lang), callback_data="o_menu:main")
    builder.adjust(1)
    return builder.as_markup()


def consultants_keyboard(consultants: list, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in consultants:
        builder.button(
            text=f"{'✅' if c.is_active else '⛔'} {c.name}",
            callback_data=f"o_consultant_detail:{c.id}"
        )
    builder.button(text=t("btn_o_add_consultant", lang), callback_data="o_consultant:new")
    builder.button(text=t("btn_main_menu", lang), callback_data="o_menu:main")
    builder.adjust(1)
    return builder.as_markup()


def consultant_detail_keyboard(lang: str, consultant_id: int, *, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.button(text=t("btn_o_remove_consultant", lang), callback_data=f"o_consultant_remove:{consultant_id}")
    else:
        builder.button(text=t("btn_o_restore_consultant", lang), callback_data=f"o_consultant_restore:{consultant_id}")
    builder.button(text=t("btn_back", lang), callback_data="o_menu:consultants")
    builder.adjust(1)
    return builder.as_markup()


def groups_owner_keyboard(groups: list, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group in groups:
        name = getattr(group, f"name_{lang}", group.name_ru)
        builder.button(text=name, callback_data=f"o_group_detail:{group.id}")
    builder.button(text=t("btn_o_new_group", lang), callback_data="o_group:new")
    builder.button(text=t("btn_main_menu", lang), callback_data="o_menu:main")
    builder.adjust(1)
    return builder.as_markup()


def group_detail_owner_keyboard(lang: str, group_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_o_delete_group", lang), callback_data=f"o_group_delete:{group_id}")
    builder.button(text=t("btn_back", lang), callback_data="o_menu:groups")
    builder.adjust(1)
    return builder.as_markup()


def consultants_for_group_keyboard(consultants: list, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for c in consultants:
        builder.button(text=c.name, callback_data=f"o_group_consultant:{c.id}")
    builder.button(text="⬜ Без ведущего", callback_data="o_group_consultant:none")
    builder.adjust(1)
    return builder.as_markup()


def feedback_period_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_period_week", lang), callback_data="o_feedback:week")
    builder.button(text=t("btn_period_month", lang), callback_data="o_feedback:month")
    builder.button(text=t("btn_period_all", lang), callback_data="o_feedback:all")
    builder.button(text=t("btn_main_menu", lang), callback_data="o_menu:main")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def counters_period_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_period_week", lang), callback_data="o_counters:week:total")
    builder.button(text=t("btn_period_month", lang), callback_data="o_counters:month:total")
    builder.button(text=t("btn_period_all", lang), callback_data="o_counters:all:total")
    builder.button(text=t("btn_by_consultant", lang), callback_data="o_counters:all:by_consultant")
    builder.button(text=t("btn_main_menu", lang), callback_data="o_menu:main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def broadcast_target_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_broadcast_all", lang), callback_data="broadcast:all")
    builder.button(text=t("btn_broadcast_consultants", lang), callback_data="broadcast:consultants")
    builder.button(text=t("btn_main_menu", lang), callback_data="o_menu:main")
    builder.adjust(1)
    return builder.as_markup()


def owner_back_keyboard(lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_main_menu", lang), callback_data="o_menu:main")
    return builder.as_markup()
