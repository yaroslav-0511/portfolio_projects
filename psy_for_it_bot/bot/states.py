from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    waiting_invite_code = State()


class SessionBookingStates(StatesGroup):
    writing_request = State()
    choosing_slot = State()
    confirming = State()


class FeedbackStates(StatesGroup):
    waiting_comment = State()


class ConsultantScheduleStates(StatesGroup):
    choosing_day = State()
    toggling_slots = State()


class OwnerCompanyStates(StatesGroup):
    entering_name = State()
    entering_limit = State()
    entering_contract_end = State()


class OwnerConsultantStates(StatesGroup):
    entering_telegram_id = State()
    entering_name = State()
    entering_specialization = State()


class OwnerGroupStates(StatesGroup):
    entering_name_ru = State()
    entering_name_en = State()
    entering_name_ua = State()
    entering_desc_ru = State()
    entering_desc_en = State()
    entering_desc_ua = State()
    choosing_consultant = State()
    entering_max_participants = State()
    entering_schedule = State()


class OwnerBroadcastStates(StatesGroup):
    entering_text = State()
    choosing_target = State()


class WellbeingStates(StatesGroup):
    """WHO-5: intro screen, 5 steps, then result (until main menu)."""

    intro = State()
    in_progress = State()
    showing_result = State()


# FSM data keys: single canonical inline-keyboard message for this chat
UI_SURFACE_MID = "ui_surface_mid"
UI_SURFACE_CID = "ui_surface_cid"
