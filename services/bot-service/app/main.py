import asyncio
import structlog
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.config import settings, fetch_telegram_config
from app.handlers import router
from app.utils.logging import setup_logging

setup_logging()
fetch_telegram_config()
logger = structlog.get_logger()


async def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("telegram_bot_token_not_set")
        return

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    logger.info("Starting bot...", service=settings.SERVICE_NAME)

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("webhook_cleared")
    except Exception as e:
        logger.warning("delete_webhook_failed", error=str(e))

    try:
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            close_bot_session=True,
            handle_signals=True,
        )
    finally:
        await bot.session.close()
        logger.info("bot_session_closed")


if __name__ == "__main__":
    asyncio.run(main())
