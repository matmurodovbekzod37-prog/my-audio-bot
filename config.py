import os
from pathlib import Path

# Telegram Bot Token (O'z botingiz tokenini shu yerga yozing)
BOT_TOKEN = "8614272291:AAFhr_cdwK7dYINsZ7vYz8HmoPO32XInlbM"
BOT_USERNAME = "@SonicAudioBot"

# Majburiy obuna uchun kanal (Monetizatsiya uchun)
# Kanal ID sini @userinfobot orqali olishingiz mumkin (masalan, -100...)
REQUIRED_CHANNEL_ID = -1001234567890 
CHANNEL_URL = "https://t.me/SizningKanalingiz"

# Admin IDs (Xatoliklar xabari uchun kerak bo'lishi mumkin)
ADMIN_IDS = [123456789] # O'zingizning Telegram ID raqamingizni yozing

# Yuklab olinadigan fayllar uchun papka
DOWNLOADS_DIR = Path(__file__).parent / "downloads"

# Papkani yaratish
if not DOWNLOADS_DIR.exists():
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Telegram fayl hajmi limiti (botlar uchun 50 MB)
# Eslatma: Local Bot API Server ishlatsangiz 2GB gacha ruxsat beradi
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
