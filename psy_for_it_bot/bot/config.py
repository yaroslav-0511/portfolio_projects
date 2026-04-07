import os
from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/mental_support"
)
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
APP_ENV: str = os.getenv("APP_ENV", "dev").strip().lower()

_owner_ids_raw = os.getenv("OWNER_TELEGRAM_IDS", "")
OWNER_TELEGRAM_IDS: list[int] = [
    int(x.strip()) for x in _owner_ids_raw.split(",") if x.strip().isdigit()
]

MAX_INVITE_ATTEMPTS: int = int(os.getenv("MAX_INVITE_ATTEMPTS", "5"))
INVITE_ATTEMPT_WINDOW: int = int(os.getenv("INVITE_ATTEMPT_WINDOW", "600"))  # seconds
_invite_limit_default = APP_ENV in ("prod", "production")
INVITE_RATE_LIMIT_ENABLED: bool = _get_bool("INVITE_RATE_LIMIT_ENABLED", _invite_limit_default)
