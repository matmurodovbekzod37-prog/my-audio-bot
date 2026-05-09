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
    """Foydalanuvchi kanalga a'zo ekanini tekshiradi."""
    if REQUIRED_CHANNEL_ID == -1001234567890: # Default qiymat bo'lsa tekshirmaymiz
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Obunani tekshirishda xato: {e}")
        return True # Xatolik bo'lsa bot ishlashda davom etsin

def get_sub_markup():
    """Obuna bo'lish tugmasini qaytaradi."""
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Obuna bo'lish 📢", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="Tasdiqlash ✅", callback_data="check_sub")]
    ])
    return markup

# Bosh menyu
def get_main_menu():
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Yordam", callback_data="help")]
    ])
    return markup

# Format tanlash menyusi
def get_format_menu(url: str):
    # Callback data limit 64 bayt, shuning uchun URL ni vaqtinchalik xotirada 
    # saqlash yoki qisqartirish kerak. Bu yerda sodda qilib faqat formatni jo'natamiz
    # va foydalanuvchi qaysi url ga javob berayotganini aniqlash uchun Reply qilinadi
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 MP3 (Audio)", callback_data="dl_audio"),
            InlineKeyboardButton(text="🎬 MP4 (Video)", callback_data="dl_video")
        ],
        [
            InlineKeyboardButton(text="🔍 Musiqani topish", callback_data="find_music")
        ]
    ])
    return markup

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "⚠️ Botdan foydalanish uchun kanalimizga obuna bo'lishingiz kerak!",
            reply_markup=get_sub_markup()
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
        # Yangi start xabarini ko'rsatish
        text = (
            f"Assalomu alaykum, {callback.from_user.first_name}! 👋\n\n"
            "Men sizga media fayllarni yuklash va musiqalarni topishda yordam beraman.\n\n"
            "✨ **Imkoniyatlarim:**\n"
            "🔗 **Link yuboring** - Instagram, YouTube, TikTok-dan MP3 yuklayman.\n"
            "🔍 **Musiqa nomi** - Istalgan qo'shiq nomini yozing, men topaman.\n"
            "🎧 **Ovozli xabar** - Musiqa parchasini yuboring, men taniyman (Shazam).\n\n"
            "📥 Boshlash uchun biron narsa yuboring!"
        )
        await callback.message.answer(text, reply_markup=get_main_menu())
    else:
        await callback.answer("❌ Siz hali obuna bo'lmagansiz!", show_alert=True)

@router.callback_query(F.data == "help")
async def process_help(callback: CallbackQuery):
    text = (
        "📖 *Yordam*\n\n"
        "1. **Link orqali:** Instagram, YouTube yoki TikTok havolasini yuboring.\n"
        "2. **Qidiruv:** Musiqa nomi yoki ijrochini yozib yuboring (masalan: `Yulduz Usmonova`)\n"
        "3. **Shazam:** Musiqa eshitilib turgan ovozli xabar yoki audioni yuboring.\n\n"
        "⚠️ *Eslatma:* Telegram botlar uchun fayl yuklash hajmi 50MB bilan cheklangan."
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@router.message(F.text)
async def handle_text(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "⚠️ Botdan foydalanish uchun kanalimizga obuna bo'lishingiz kerak!",
            reply_markup=get_sub_markup()
        )
        return
    urls = extract_urls(message.text)
    
    if urls:
        # Faqat birinchi linkni olamiz
        url = urls[0]
        # URL ni tasdiqlab, format tanlashni so'raymiz
        text = f"Havola qabul qilindi. Qaysi formatda yuklab olmoqchisiz?\n\n{url}"
        await message.reply(text, reply_markup=get_format_menu(url), disable_web_page_preview=True)
    else:
        # Agar link bo'lmasa, uni qidiruv so'rovi deb hisoblaymiz
        query = message.text.strip()
        if len(query) < 2:
            return

        status_msg = await message.reply(f"🔍 **{query}** qidirilmoqda, iltimos kuting...")
        
        # Qidirish va yuklab olish
        result = await search_and_download_audio(query)
        
        if not result['success']:
            error_msg = result.get('error', "Musiqa topilmadi.")
            await status_msg.edit_text(f"❌ {error_msg}")
            return
            
        file_path = result['file_path']
        title = result['title']
        
        try:
            # Fayl hajmini tekshirish
            file_size = os.path.getsize(file_path)
            
            if file_size > MAX_FILE_SIZE_BYTES:
                await status_msg.edit_text(
                    f"⚠️ Topilgan fayl hajmi juda katta ({file_size // (1024*1024)} MB)!\n"
                    "Bot orqali faqat 50MB gacha fayllarni yuborish mumkin."
                )
            else:
                await status_msg.edit_text("📤 Telegramga yuklanmoqda...")
                
                media = FSInputFile(file_path)
                await bot.send_audio(
                    chat_id=message.chat.id,
                    audio=media,
                    caption=f"🎧 {title}\n\n🤖 {BOT_USERNAME}",
                    reply_to_message_id=message.message_id
                )
                
                # Holat xabarini o'chirish
                await status_msg.delete()
                
        except Exception as e:
            logger.error(f"Qidiruv natijasini yuborishda xatolik: {e}")
            await status_msg.edit_text("❌ Musiqani yuborishda xatolik yuz berdi.")
        finally:
            # Faylni serverdan o'chirish
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Faylni o'chirishda xatolik: {e}")

@router.callback_query(F.data.in_(["dl_audio", "dl_video"]))
async def process_download(callback: CallbackQuery, bot: Bot):
    format_type = "audio" if callback.data == "dl_audio" else "video"
    
    # URL ni callback.message.text dan olish
    # Xabar formati: "Havola qabul qilindi. Qaysi formatda yuklab olmoqchisiz?\n\nURL"
    original_text = callback.message.text
    urls = extract_urls(original_text)
    
    if not urls:
        await callback.answer("Havola topilmadi!", show_alert=True)
        return
        
    url = urls[0]
    
    await callback.message.edit_text("⏳ Yuklab olinmoqda... Iltimos kuting.")
    
    # Yuklab olishni boshlash
    result = await download_media(url, format_type)
    
    if not result['success']:
        error_msg = result.get('error', "Noma'lum xato")
        await callback.message.edit_text(f"❌ Xatolik yuz berdi:\n\n{error_msg}")
        return
        
    file_path = result['file_path']
    title = result['title']
    
    try:
        # Fayl hajmini tekshirish
        file_size = os.path.getsize(file_path)
        
        if file_size > MAX_FILE_SIZE_BYTES:
            await callback.message.edit_text(
                f"⚠️ Fayl hajmi juda katta ({file_size // (1024*1024)} MB)!\n"
                f"Telegram bot orqali faqat 50MB gacha fayllarni yuborish mumkin."
            )
        else:
            await callback.message.edit_text("📤 Telegramga yuklanmoqda...")
            
            media = FSInputFile(file_path)
            if format_type == 'audio':
                await bot.send_audio(
                    chat_id=callback.message.chat.id,
                    audio=media,
                    caption=f"🎵 {title}\n\n🤖 {BOT_USERNAME}",
                    reply_to_message_id=callback.message.reply_to_message.message_id if callback.message.reply_to_message else None
                )
            else:
                await bot.send_video(
                    chat_id=callback.message.chat.id,
                    video=media,
                    caption=f"🎬 {title}\n\n🤖 {BOT_USERNAME}",
                    reply_to_message_id=callback.message.reply_to_message.message_id if callback.message.reply_to_message else None
                )
            
            # Yuklab olinganidan so'ng xabarni o'chirish
            await callback.message.delete()
            
    except Exception as e:
        logger.error(f"Telegramga yuborishda xatolik: {e}")
        await callback.message.edit_text("❌ Faylni Telegramga yuborishda xatolik yuz berdi.")
        
    finally:
        # Yuklab olingan faylni serverdan o'chirish
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Faylni o'chirishda xatolik: {e}")

@router.callback_query(F.data == "find_music")
async def process_find_music(callback: CallbackQuery, bot: Bot):
    original_text = callback.message.text
    urls = extract_urls(original_text)
    
    if not urls:
        await callback.answer("Havola topilmadi!", show_alert=True)
        return
        
    url = urls[0]
    
    await callback.message.edit_text("⏳ Videodagi musiqa qidirilmoqda... Iltimos kuting.")
    
    # 1. Avval videodan audioni vaqtinchalik yuklab olamiz
    result = await download_media(url, "audio")
    
    if not result['success']:
        error_msg = result.get('error', "Noma'lum xato")
        await callback.message.edit_text(f"❌ Yuklab olishda xatolik yuz berdi:\n\n{error_msg}")
        return
        
    temp_file_path = result['file_path']
    
    try:
        # 2. Shazam orqali musiqani aniqlash
        await callback.message.edit_text("🎵 Musiqa tahlil qilinmoqda (Shazam)...")
        shazam_result = await recognize_song(temp_file_path)
        
        if not shazam_result['success']:
            error_msg = shazam_result.get('error', "Noma'lum xato")
            await callback.message.edit_text(f"❌ Musiqa topilmadi:\n\n{error_msg}")
            return
            
        full_name = shazam_result['full_name']
        await callback.message.edit_text(f"✅ Musiqa topildi: **{full_name}**\n\n📥 To'liq versiyasi yuklab olinmoqda...")
        
        # 3. Topilgan musiqani YouTube dan izlash va yuklab olish
        search_result = await search_and_download_audio(full_name)
        
        if not search_result['success']:
            error_msg = search_result.get('error', "Noma'lum xato")
            await callback.message.edit_text(f"❌ Topilgan musiqani yuklab olish imkoni bo'lmadi:\n\n{error_msg}")
            return
            
        final_file_path = search_result['file_path']
        
        try:
            # Fayl hajmini tekshirish
            file_size = os.path.getsize(final_file_path)
            
            if file_size > MAX_FILE_SIZE_BYTES:
                await callback.message.edit_text(
                    f"⚠️ Fayl hajmi juda katta ({file_size // (1024*1024)} MB)!\n"
                )
            else:
                await callback.message.edit_text("📤 Telegramga yuborilmoqda...")
                
                media = FSInputFile(final_file_path)
                await bot.send_audio(
                    chat_id=callback.message.chat.id,
                    audio=media,
                    caption=f"🎧 {full_name}\n\n🤖 {BOT_USERNAME}",
                    reply_to_message_id=callback.message.reply_to_message.message_id if callback.message.reply_to_message else None
                )
                
                # O'chirish
                await callback.message.delete()
                
        except Exception as e:
            logger.error(f"Telegramga yuborishda xatolik: {e}")
            await callback.message.edit_text("❌ Faylni Telegramga yuborishda xatolik yuz berdi.")
        finally:
            if os.path.exists(final_file_path):
                try:
                    os.remove(final_file_path)
                except Exception as e:
                    logger.error(f"Faylni o'chirishda xatolik: {e}")
                    
    except Exception as e:
        logger.error(f"Shazam jarayonida xatolik: {e}")
        await callback.message.edit_text("❌ Musiqani aniqlashda xatolik yuz berdi.")
    finally:
        # Vaqtinchalik faylni o'chirish
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.error(f"Vaqtinchalik faylni o'chirishda xatolik: {e}")
@router.message(F.audio | F.voice)
async def handle_audio_voice(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "⚠️ Botdan foydalanish uchun kanalimizga obuna bo'lishingiz kerak!",
            reply_markup=get_sub_markup()
        )
        return
    """Audio fayl yoki ovozli xabar orqali musiqani taniydi."""
    status_msg = await message.reply("⏳ Musiqa tahlil qilinmoqda... Iltimos kuting.")
    
    try:
        # 1. Telegramdan faylni yuklab olish
        file_id = message.audio.file_id if message.audio else message.voice.file_id
        file = await bot.get_file(file_id)
        
        # Vaqtinchalik fayl manzili
        from config import DOWNLOADS_DIR
        ext = "mp3" if message.audio else "ogg"
        temp_file_name = f"rec_{uuid.uuid4()}.{ext}"
        temp_file_path = os.path.join(DOWNLOADS_DIR, temp_file_name)
        
        await bot.download_file(file.file_path, temp_file_path)
        
        # 2. Shazam orqali aniqlash
        await status_msg.edit_text("🎵 Musiqa tahlil qilinmoqda (Shazam)...")
        shazam_result = await recognize_song(temp_file_path)
        
        if not shazam_result['success']:
            error_msg = shazam_result.get('error', "Musiqa topilmadi.")
            await status_msg.edit_text(f"❌ {error_msg}")
            return
            
        full_name = shazam_result['full_name']
        await status_msg.edit_text(f"✅ Musiqa topildi: **{full_name}**\n\n📥 To'liq versiyasi yuklab olinmoqda...")
        
        # 3. Topilgan musiqani YouTube/SoundCloud dan izlash va yuklab olish
        search_result = await search_and_download_audio(full_name)
        
        if not search_result['success']:
            error_msg = search_result.get('error', "Yuklab olishda xatolik.")
            await status_msg.edit_text(f"❌ {full_name} topildi, lekin uni yuklab olish imkoni bo'lmadi.")
            return
            
        final_file_path = search_result['file_path']
        
        try:
            # Fayl hajmini tekshirish
            file_size = os.path.getsize(final_file_path)
            
            if file_size > MAX_FILE_SIZE_BYTES:
                await status_msg.edit_text(
                    f"⚠️ Topilgan fayl hajmi juda katta ({file_size // (1024*1024)} MB)!"
                )
            else:
                await status_msg.edit_text("📤 Telegramga yuborilmoqda...")
                
                media = FSInputFile(final_file_path)
                await bot.send_audio(
                    chat_id=message.chat.id,
                    audio=media,
                    caption=f"🎧 {full_name}\n\n🤖 {BOT_USERNAME}",
                    reply_to_message_id=message.message_id
                )
                
                await status_msg.delete()
                
        except Exception as e:
            logger.error(f"Audio recognition natijasini yuborishda xatolik: {e}")
            await status_msg.edit_text("❌ Musiqani yuborishda xatolik yuz berdi.")
        finally:
            if os.path.exists(final_file_path):
                os.remove(final_file_path)
                
    except Exception as e:
        logger.error(f"Audio/Voice recognition jarayonida xatolik: {e}")
        await status_msg.edit_text("❌ Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")
    finally:
        # Vaqtinchalik faylni o'chirish
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
