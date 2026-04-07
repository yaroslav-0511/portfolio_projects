import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import BOT_TOKEN, REDIS_URL
from bot.database.migrations import run_migrations
from bot.database.session import verify_db_connection
from bot.handlers import common, consultant, owner, user, wellbeing
from bot.i18n import load_translations
from bot.middlewares.auth import AuthMiddleware, ProxyRelayMiddleware
from bot.middlewares.ui_surface import UiSurfaceMiddleware
from bot.services.scheduler import get_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is not set in environment! Check your .env file.")
        sys.exit(1)

    # Load translations
    load_translations()
    logger.info("Translations loaded")

    # Verify DB connectivity (migrations are applied before event loop starts)
    await verify_db_connection()
    logger.info("Database connection verified")

    # Set up bot & dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)

    # Register middlewares on the update level
    dp.update.outer_middleware(AuthMiddleware())
    dp.update.outer_middleware(ProxyRelayMiddleware())
    dp.callback_query.middleware(UiSurfaceMiddleware())

    # Include routers (order matters — common first for /start)
    dp.include_router(common.router)
    dp.include_router(user.router)
    dp.include_router(wellbeing.router)
    dp.include_router(consultant.router)
    dp.include_router(owner.router)

    # Start scheduler
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    logger.info("Bot starting polling...")
    try:
        # Sequential updates avoid FSM read-modify-write races (e.g. WHO-5 double taps).
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_as_tasks=False,
        )
    finally:
        scheduler.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    run_migrations()
    asyncio.run(main())
