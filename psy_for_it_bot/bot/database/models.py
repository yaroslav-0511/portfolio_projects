import enum
from datetime import datetime, timezone


def _utcnow() -> datetime:
    """Return current UTC time as a naive datetime (for storage in DB)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime,
    Enum, ForeignKey, Integer, SmallInteger, String, Text, Time,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    USER = "U"
    CONSULTANT = "C"
    OWNER = "O"


class InviteCodeStatus(str, enum.Enum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


class InviteCodeType(str, enum.Enum):
    USER = "user"
    CONSULTANT = "consultant"


class SessionType(str, enum.Enum):
    URGENT = "urgent"
    PLANNED = "planned"
    GROUP = "group"


class SessionStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class CompanyStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    ENDED = "ended"


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    max_users = Column(Integer, nullable=False, default=10)
    contract_start = Column(Date, nullable=True)
    contract_end = Column(Date, nullable=True)
    status = Column(Enum(CompanyStatus), default=CompanyStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    invite_codes = relationship("InviteCode", back_populates="company")
    users = relationship("User", back_populates="company")


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    status = Column(Enum(InviteCodeStatus), default=InviteCodeStatus.ACTIVE, nullable=False)
    # Store raw telegram_id (no FK): invite can be activated by a new user not yet committed.
    activated_by = Column(BigInteger, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    type = Column(Enum(InviteCodeType), default=InviteCodeType.USER, nullable=False)

    company = relationship("Company", back_populates="invite_codes")


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    language = Column(String(2), default="ru", nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    last_active_at = Column(DateTime, default=_utcnow, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="users")
    consultant_profile = relationship(
        "Consultant", back_populates="user", uselist=False,
        foreign_keys="Consultant.user_id"
    )
    sessions_as_user = relationship(
        "Session", back_populates="user", foreign_keys="Session.user_id"
    )
    feedbacks = relationship("Feedback", back_populates="user", foreign_keys="Feedback.user_id")
    group_registrations = relationship("GroupRegistration", back_populates="user")
    wellbeing_responses = relationship("WellbeingResponse", back_populates="user")


class Consultant(Base):
    __tablename__ = "consultants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    specialization = Column(String(500), nullable=True)
    bio = Column(Text, nullable=True)
    max_slots_per_week = Column(Integer, default=20, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="consultant_profile", foreign_keys=[user_id])
    schedule_slots = relationship("ScheduleSlot", back_populates="consultant")
    sessions = relationship("Session", back_populates="consultant", foreign_keys="Session.consultant_id")
    groups = relationship("SupportGroup", back_populates="consultant")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    consultant_id = Column(Integer, ForeignKey("consultants.id"), nullable=True)
    slot_id = Column(Integer, ForeignKey("schedule_slots.id"), nullable=True)
    type = Column(Enum(SessionType), nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.PENDING, nullable=False)
    request_text = Column(Text, nullable=True)
    confirmed_by_user = Column(Boolean, default=False, nullable=False)
    confirmed_by_consultant = Column(Boolean, default=False, nullable=False)
    cancellation_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    user = relationship("User", back_populates="sessions_as_user", foreign_keys=[user_id])
    consultant = relationship("Consultant", back_populates="sessions", foreign_keys=[consultant_id])
    slot = relationship("ScheduleSlot")
    feedback = relationship("Feedback", back_populates="session", uselist=False)


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    rating = Column(SmallInteger, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    session = relationship("Session", back_populates="feedback")
    user = relationship("User", back_populates="feedbacks", foreign_keys=[user_id])


class SupportGroup(Base):
    __tablename__ = "support_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name_en = Column(String(255), nullable=False)
    name_ua = Column(String(255), nullable=False)
    name_ru = Column(String(255), nullable=False)
    description_en = Column(Text, nullable=True)
    description_ua = Column(Text, nullable=True)
    description_ru = Column(Text, nullable=True)
    consultant_id = Column(Integer, ForeignKey("consultants.id"), nullable=True)
    max_participants = Column(Integer, default=20, nullable=False)
    schedule = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    consultant = relationship("Consultant", back_populates="groups")
    registrations = relationship("GroupRegistration", back_populates="group")


class GroupRegistration(Base):
    __tablename__ = "group_registrations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("support_groups.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    registered_at = Column(DateTime, default=_utcnow, nullable=False)

    group = relationship("SupportGroup", back_populates="registrations")
    user = relationship("User", back_populates="group_registrations")


class WellbeingResponse(Base):
    """Stored WHO-5 result (raw score 0–25)."""

    __tablename__ = "wellbeing_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    score_raw = Column(SmallInteger, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    user = relationship("User", back_populates="wellbeing_responses")


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    consultant_id = Column(Integer, ForeignKey("consultants.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_booked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    consultant = relationship("Consultant", back_populates="schedule_slots")


class ActiveConversation(Base):
    __tablename__ = "active_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    consultant_telegram_id = Column(BigInteger, nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    conv_type = Column(String(20), default="urgent", nullable=False)
    started_at = Column(DateTime, default=_utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(Enum(ConversationStatus), default=ConversationStatus.ACTIVE, nullable=False)

    session = relationship("Session")
