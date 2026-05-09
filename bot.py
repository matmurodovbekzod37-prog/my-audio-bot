import asyncio
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from handlers import router

# Dummy HTTP server Render uchun (o'chib qolmasligi uchun)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_health_check():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Logging sozlamalari
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    if BOT_TOKEN == "SIZNING_BOT_TOKENINGIZ_SHU_YERDA":
        logger.error("Iltimos, config.py fayliga bot tokenini kiriting!")
        return

    # Render uchun HTTP serverni alohida oqimda ishga tushirish
    threading.Thread(target=run_health_check, daemon=True).start()

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
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
