import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from handlers import router

# Logging sozlamalari
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    if BOT_TOKEN == "SIZNING_BOT_TOKENINGIZ_SHU_YERDA":
        logger.error("Iltimos, config.py fayliga bot tokenini kiriting!")
        return

    # Bot va Dispatcher yaratish
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Routerni ulash
    dp.include_router(router)
    
    logger.info("Bot ishga tushdi...")
    
    # Pollingni boshlash
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
