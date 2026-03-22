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

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
storage = RedisStorage.from_url(settings.REDIS_URL)
dp = Dispatcher(storage=storage)

router.message.filter()
dp.include_router(router)


async def main() -> None:
    logger.info("bot_started", service=settings.SERVICE_NAME)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
