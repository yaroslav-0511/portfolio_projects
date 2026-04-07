import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore

from bot.config import REDIS_URL

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {
            "default": RedisJobStore(
                host=_parse_redis_host(REDIS_URL),
                port=_parse_redis_port(REDIS_URL),
                db=_parse_redis_db(REDIS_URL),
            )
        }
        _scheduler = AsyncIOScheduler(jobstores=jobstores)
    return _scheduler


def _parse_redis_host(url: str) -> str:
    try:
        return url.split("//")[1].split(":")[0]
    except (IndexError, AttributeError):
        return "localhost"


def _parse_redis_port(url: str) -> int:
    try:
        part = url.split("//")[1]
        return int(part.split(":")[1].split("/")[0])
    except (IndexError, ValueError, AttributeError):
        return 6379


def _parse_redis_db(url: str) -> int:
    try:
        return int(url.rsplit("/", 1)[-1])
    except (ValueError, IndexError):
        return 0


async def schedule_session_reminders(
    bot_token: str,
    user_telegram_id: int,
    session_id: int,
    scheduled_at: datetime,
    session_time_str: str,
    lang: str,
) -> None:
    """Schedule reminder jobs for a session."""
    scheduler = get_scheduler()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    reminder_offsets = [
        (timedelta(days=7), "reminder_7d"),
        (timedelta(days=3), "reminder_3d"),
        (timedelta(hours=24), "reminder_24h"),
        (timedelta(hours=1), "reminder_1h"),
    ]

    for offset, reminder_key in reminder_offsets:
        run_time = scheduled_at - offset
        if run_time > now:
            job_id = f"reminder_{session_id}_{reminder_key}"
            scheduler.add_job(
                _send_reminder,
                trigger="date",
                run_date=run_time,
                args=[bot_token, user_telegram_id, session_id, reminder_key, session_time_str, lang],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=300,
            )

    # Post-session check (5 min after scheduled time)
    post_time = scheduled_at + timedelta(minutes=5)
    if post_time > now:
        scheduler.add_job(
            _send_post_session_check,
            trigger="date",
            run_date=post_time,
            args=[bot_token, user_telegram_id, session_id, lang],
            id=f"post_session_{session_id}",
            replace_existing=True,
            misfire_grace_time=600,
        )


async def _send_reminder(
    bot_token: str,
    user_telegram_id: int,
    session_id: int,
    reminder_key: str,
    session_time_str: str,
    lang: str,
) -> None:
    from aiogram import Bot
    from bot.i18n import t
    from bot.keyboards.user_kb import reminder_keyboard

    bot = Bot(token=bot_token)
    try:
        text = t(reminder_key, lang, time=session_time_str)
        kb = reminder_keyboard(lang, session_id)
        await bot.send_message(user_telegram_id, text, reply_markup=kb)
    except Exception as e:
        logger.error(f"Failed to send reminder {reminder_key} to {user_telegram_id}: {e}")
    finally:
        await bot.session.close()


async def _send_post_session_check(
    bot_token: str,
    user_telegram_id: int,
    session_id: int,
    lang: str,
) -> None:
    from aiogram import Bot
    from bot.i18n import t
    from bot.keyboards.user_kb import post_session_keyboard

    bot = Bot(token=bot_token)
    try:
        text = t("post_session_prompt", lang)
        kb = post_session_keyboard(lang, session_id)
        await bot.send_message(user_telegram_id, text, reply_markup=kb)
    except Exception as e:
        logger.error(f"Failed to send post-session check to {user_telegram_id}: {e}")
    finally:
        await bot.session.close()


def cancel_session_jobs(session_id: int) -> None:
    scheduler = get_scheduler()
    keys = [
        f"reminder_{session_id}_reminder_7d",
        f"reminder_{session_id}_reminder_3d",
        f"reminder_{session_id}_reminder_24h",
        f"reminder_{session_id}_reminder_1h",
        f"post_session_{session_id}",
    ]
    for key in keys:
        try:
            scheduler.remove_job(key)
        except Exception as e:
            logger.debug(f"Job {key} not found or already removed: {e}")
