from datetime import date, datetime, timedelta

from bot.database.models import Consultant, Session, SessionStatus, SessionType, User, UserRole
from bot.services.consultant_lifecycle import (
    cancel_future_sessions,
    deactivate_consultant_account,
    is_slot_visible_for_booking,
    restore_consultant_role,
)


def _make_session(*, status: SessionStatus, scheduled_at: datetime | None, reason: str | None = None) -> Session:
    return Session(
        user_id=1,
        consultant_id=1,
        type=SessionType.PLANNED,
        status=status,
        scheduled_at=scheduled_at,
        cancellation_reason=reason,
    )


def test_cancel_future_sessions_only_future_pending_and_confirmed() -> None:
    now = datetime(2026, 3, 27, 12, 0, 0)
    sessions = [
        _make_session(status=SessionStatus.PENDING, scheduled_at=now + timedelta(hours=1)),
        _make_session(status=SessionStatus.CONFIRMED, scheduled_at=now + timedelta(days=1)),
        _make_session(status=SessionStatus.COMPLETED, scheduled_at=now + timedelta(hours=2)),
        _make_session(status=SessionStatus.NO_SHOW, scheduled_at=now + timedelta(hours=2)),
        _make_session(status=SessionStatus.PENDING, scheduled_at=now - timedelta(hours=1)),
        _make_session(status=SessionStatus.PENDING, scheduled_at=None),
    ]

    changed = cancel_future_sessions(sessions, now=now)

    assert changed == 2
    assert sessions[0].status == SessionStatus.CANCELLED
    assert sessions[1].status == SessionStatus.CANCELLED
    assert sessions[2].status == SessionStatus.COMPLETED
    assert sessions[3].status == SessionStatus.NO_SHOW
    assert sessions[4].status == SessionStatus.PENDING
    assert sessions[5].status == SessionStatus.PENDING


def test_cancel_future_sessions_keeps_existing_reason() -> None:
    now = datetime(2026, 3, 27, 12, 0, 0)
    session = _make_session(
        status=SessionStatus.CONFIRMED,
        scheduled_at=now + timedelta(hours=2),
        reason="Manual cancellation note",
    )

    changed = cancel_future_sessions([session], now=now)

    assert changed == 1
    assert session.status == SessionStatus.CANCELLED
    assert session.cancellation_reason == "Manual cancellation note"


def test_restore_consultant_role_sets_active_and_user_role() -> None:
    consultant = Consultant(user_id=123, name="C", specialization=None, is_active=False)
    user_obj = User(telegram_id=123, role=UserRole.USER, language="ru")

    restore_consultant_role(consultant, user_obj)

    assert consultant.is_active is True
    assert user_obj.role == UserRole.CONSULTANT


def test_slot_visibility_for_booking_requires_active_consultant_and_free_future_slot() -> None:
    today = date(2026, 3, 27)

    assert is_slot_visible_for_booking(
        slot_date=today,
        is_booked=False,
        consultant_is_active=True,
        today=today,
    )
    assert not is_slot_visible_for_booking(
        slot_date=today,
        is_booked=True,
        consultant_is_active=True,
        today=today,
    )
    assert not is_slot_visible_for_booking(
        slot_date=today,
        is_booked=False,
        consultant_is_active=False,
        today=today,
    )
    assert not is_slot_visible_for_booking(
        slot_date=today - timedelta(days=1),
        is_booked=False,
        consultant_is_active=True,
        today=today,
    )


def test_deactivate_consultant_account_updates_user_groups_and_cancels_future_sessions() -> None:
    now = datetime(2026, 3, 27, 12, 0, 0)
    consultant = Consultant(id=7, user_id=123, name="C", specialization=None, is_active=True)
    user_obj = User(telegram_id=123, role=UserRole.CONSULTANT, language="ru", company_id=5, is_blocked=False)

    class _Group:
        def __init__(self, consultant_id: int | None):
            self.consultant_id = consultant_id

    groups = [_Group(7), _Group(7)]
    sessions = [
        _make_session(status=SessionStatus.PENDING, scheduled_at=now + timedelta(hours=1)),
        _make_session(status=SessionStatus.CONFIRMED, scheduled_at=now + timedelta(days=1)),
        _make_session(status=SessionStatus.COMPLETED, scheduled_at=now + timedelta(days=1)),
    ]

    cancelled = deactivate_consultant_account(
        consultant=consultant,
        user_obj=user_obj,
        groups=groups,
        future_sessions=sessions,
        now=now,
    )

    assert cancelled == 2
    assert consultant.is_active is False
    assert all(g.consultant_id is None for g in groups)
    assert user_obj.is_deleted is True
    assert user_obj.is_blocked is True
    assert user_obj.company_id is None
    assert user_obj.role == UserRole.USER
    assert sessions[0].status == SessionStatus.CANCELLED
    assert sessions[1].status == SessionStatus.CANCELLED
    assert sessions[2].status == SessionStatus.COMPLETED

