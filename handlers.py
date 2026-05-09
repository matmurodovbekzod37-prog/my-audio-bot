import os
import logging
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, Command
from utils import extract_urls
from downloader import download_media, search_and_download_audio
from shazam_utils import recognize_song
from config import MAX_FILE_SIZE_BYTES, BOT_USERNAME, REQUIRED_CHANNEL_ID, CHANNEL_URL

router = Router()
logger = logging.getLogger(__name__)

async def check_subscription(bot: Bot, user_id: int) -> bool:
    if REQUIRED_CHANNEL_ID == -1001234567890:
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Obunani tekshirishda xato: {e}")
        return True

def get_sub_markup():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Kanalga obuna bo'lish 📢", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="Tasdiqlash ✅", callback_data="check_sub")]
    ])

def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Yordam va Qo'llanma", callback_data="help")],
        [InlineKeyboardButton(text="⭐️ Botni ulashish", url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}&text=Zo'r audiobot ekan, tavsiya qilaman!")]
    ])

def get_format_menu(url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 MP3 (Musiqa)", callback_data="dl_audio"),
            InlineKeyboardButton(text="🎬 MP4 (Video)", callback_data="dl_video")
        ]
    ])

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "⚠️ **Botdan foydalanish uchun kanalimizga obuna bo'lishingiz kerak!**\n\n"
            "Obuna bo'lgach, 'Tasdiqlash' tugmasini bosing.",
            reply_markup=get_sub_markup(),
            parse_mode="Markdown"
        )
        return

    text = (
        f"Assalomu alaykum, {message.from_user.first_name}! 👋\n\n"
        "Men sizga media fayllarni yuklash va musiqalarni topishda yordam beraman.\n\n"
        "✨ **Imkoniyatlarim:**\n"
        "🔗 **Link yuboring** - Instagram, YouTube, TikTok-dan MP3 yuklayman.\n"
        "🔍 **Musiqa nomi** - Istalgan qo'shiq nomini yozing, men topaman.\n"
        "🎧 **Ovozli xabar** - Musiqa parchasini yuboring, men taniyman (Shazam).\n\n"
        "📥 Boshlash uchun biron narsa yuboring!"
    )
    await message.answer(text, reply_markup=get_main_menu())

@router.callback_query(F.data == "check_sub")
async def process_check_sub(callback: CallbackQuery, bot: Bot):
    if await check_subscription(bot, callback.from_user.id):
        await callback.message.edit_text("✅ Raxmat! Endi botdan foydalanishingiz mumkin.")
        await cmd_start(callback.message, bot)
    else:
        await callback.answer("❌ Siz hali obuna bo'lmagansiz!", show_alert=True)

@router.callback_query(F.data == "help")
async def process_help(callback: CallbackQuery):
    text = (
        "📖 **Yordam va Qo'llanma**\n\n"
        "1. **Link orqali:** Instagram, YouTube yoki TikTok havolasini yuboring.\n"
        "2. **Qidiruv:** Musiqa nomi yoki ijrochini yozib yuboring (masalan: `Yulduz Usmonova`)\n"
        "3. **Shazam:** Musiqa eshitilib turgan ovozli xabar yoki audioni yuboring.\n\n"
        "⚠️ **Eslatma:** Telegram botlar uchun fayl yuklash hajmi 50MB bilan cheklangan."
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@router.message(F.text)
async def handle_text(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer("⚠️ Avval kanalga obuna bo'ling!", reply_markup=get_sub_markup())
        return

    urls = extract_urls(message.text)
    if urls:
        url = urls[0]
        sent_message = await message.answer("⏳ **Link tahlil qilinmoqda...**", parse_mode="Markdown")
        result = await download_media(url, 'audio')
        if result['status'] == 'success':
            audio = FSInputFile(result['filepath'])
            caption = f"🎵 **{result['title']}**\n\n📥 @{BOT_USERNAME} orqali yuklandi"
            await message.answer_audio(audio, caption=caption, parse_mode="Markdown")
            await sent_message.delete()
            if os.path.exists(result['filepath']): os.remove(result['filepath'])
        else:
            await sent_message.edit_text(f"❌ **Xatolik:** {result['message']}")
        return

    # Aqlli qidiruv filtri
    query = message.text.strip()
    if len(query) < 3 or query.startswith('/') or query.startswith('.'):
        await message.answer("❓ **Tushunmadim.** Iltimos, musiqa nomini to'liq yozing yoki link yuboring.")
        return

    sent_message = await message.answer(f"🔍 **'{query}'** qidirilmoqda, iltimos kuting...", parse_mode="Markdown")
    result = await search_and_download_audio(query)
    if result['status'] == 'success':
        audio = FSInputFile(result['filepath'])
        caption = f"✅ **Topildi:** {result['title']}\n\n🤖 @{BOT_USERNAME}"
        await message.answer_audio(audio, caption=caption, parse_mode="Markdown")
        await sent_message.delete()
        if os.path.exists(result['filepath']): os.remove(result['filepath'])
    else:
        await sent_message.edit_text(f"😔 **'{query}'** topilmadi. Boshqacha yozib ko'ring.")

@router.message(F.voice | F.audio)
async def handle_audio(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer("⚠️ Avval kanalga obuna bo'ling!", reply_markup=get_sub_markup())
        return

    sent_message = await message.answer("🎧 **Musiqa tanilmoqda (Shazam)...**", parse_mode="Markdown")
    
    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    file_path = os.path.join(DOWNLOADS_DIR, f"{uuid.uuid4()}.ogg")
    await bot.download_file(file.file_path, file_path)

    shazam_result = await recognize_song(file_path)
    if os.path.exists(file_path): os.remove(file_path)

    if shazam_result['status'] == 'success':
        title = shazam_result['title']
        subtitle = shazam_result['subtitle']
        await sent_message.edit_text(f"✅ **Topildi!**\n\n🎼 **Nomi:** {title}\n👤 **Ijrochi:** {subtitle}\n\n⏳ Endi uni yuklab beraman...")
        
        result = await search_and_download_audio(f"{title} {subtitle}")
        if result['status'] == 'success':
            audio = FSInputFile(result['filepath'])
            await message.answer_audio(audio, caption=f"✨ **{title}** - {subtitle}\n\n📥 @{BOT_USERNAME}")
            if os.path.exists(result['filepath']): os.remove(result['filepath'])
        else:
            await message.answer(f"😔 Kechirasiz, musiqani topdimu, lekin yuklashda xato bo'ldi.")
    else:
        await sent_message.edit_text("❌ **Musiqa tanilmadi.** Ovoz baland va aniqroq bo'lishiga e'tibor bering.")
