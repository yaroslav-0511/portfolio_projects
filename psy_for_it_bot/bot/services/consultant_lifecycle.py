from datetime import date, datetime

from bot.database.models import Consultant, Session, SessionStatus, User, UserRole


def cancel_future_sessions(
    sessions: list[Session],
    *,
    now: datetime,
    reason: str = "Consultant account deleted",
) -> int:
    """Cancel future pending/confirmed sessions for deactivated consultant."""
    changed = 0
    for sess in sessions:
        if (
            sess.scheduled_at is not None
            and sess.scheduled_at > now
            and sess.status in (SessionStatus.PENDING, SessionStatus.CONFIRMED)
        ):
            sess.status = SessionStatus.CANCELLED
            if not sess.cancellation_reason:
                sess.cancellation_reason = reason
            changed += 1
    return changed


def restore_consultant_role(consultant: Consultant, user_obj: User | None) -> None:
    """Restore deactivated consultant and sync user role."""
    consultant.is_active = True
    if user_obj:
        user_obj.role = UserRole.CONSULTANT


def deactivate_consultant_account(
    *,
    consultant: Consultant | None,
    user_obj: User | None,
    groups: list,
    future_sessions: list[Session],
    now: datetime,
) -> int:
    """Deactivate consultant account and return number of cancelled sessions."""
    if consultant is not None:
        consultant.is_active = False
        for group in groups:
            group.consultant_id = None
        cancelled = cancel_future_sessions(future_sessions, now=now)
    else:
        cancelled = 0

    if user_obj is not None:
        user_obj.is_deleted = True
        user_obj.deleted_at = now
        user_obj.is_blocked = True
        user_obj.company_id = None
        user_obj.role = UserRole.USER

    return cancelled


def is_slot_visible_for_booking(
    *,
    slot_date: date,
    is_booked: bool,
    consultant_is_active: bool,
    today: date,
) -> bool:
    """Return whether a slot should be visible for user booking."""
    return slot_date >= today and (not is_booked) and consultant_is_active

