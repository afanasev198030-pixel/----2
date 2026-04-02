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


async def run_notify_server(bot: Bot):
    """Run lightweight FastAPI server for push notifications on port 8006."""
    import uvicorn
    from app.notify_server import app as notify_app, set_bot

    set_bot(bot)
    config = uvicorn.Config(notify_app, host="0.0.0.0", port=8006, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()


async def run_bot(bot: Bot, dp: Dispatcher):
    """Run aiogram long-polling."""
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("webhook_cleared")
    except Exception as e:
        logger.warning("delete_webhook_failed", error=str(e))

    await dp.start_polling(
        bot,
        allowed_updates=["message", "callback_query"],
        close_bot_session=False,
        handle_signals=False,
    )


async def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("telegram_bot_token_not_set")
        return

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    storage = RedisStorage.from_url(settings.REDIS_URL)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    logger.info("Starting bot + notify server...", service=settings.SERVICE_NAME)

    try:
        await asyncio.gather(
            run_bot(bot, dp),
            run_notify_server(bot),
        )
    finally:
        await bot.session.close()
        logger.info("bot_session_closed")


if __name__ == "__main__":
    asyncio.run(main())
