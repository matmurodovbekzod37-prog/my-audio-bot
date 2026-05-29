import os
import logging
import uuid
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import CommandStart, Command
from utils import extract_urls
from downloader import download_media, get_search_results, download_audio_by_url
from shazam_utils import recognize_song
from database import db_cache
from config import MAX_FILE_SIZE_BYTES, BOT_USERNAME, REQUIRED_CHANNEL_ID, CHANNEL_URL, DOWNLOADS_DIR

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

# Foydalanuvchi qidiruv natijalarini vaqtinchalik saqlash uchun
user_searches = {}

def get_search_keyboard(results_count: int):
    keyboard = []
    # Raqamli tugmalarni 5 tadan qilib 2 qatorga teramiz
    row1 = [InlineKeyboardButton(text=str(i+1), callback_data=f"dl_idx_{i}") for i in range(min(5, results_count))]
    row2 = [InlineKeyboardButton(text=str(i+1), callback_data=f"dl_idx_{i}") for i in range(5, min(10, results_count))]
    if row1: keyboard.append(row1)
    if row2: keyboard.append(row2)
    # Bekor qilish tugmasi
    keyboard.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_search")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def format_duration(seconds: int) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"

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
        "Men sizga musiqalarni topish va yuklashda yordam beraman.\n\n"
        "✨ **Imkoniyatlarim:**\n"
        "🔍 **Musiqa nomi** - Istalgan qo'shiq nomini yozing, men topaman.\n"
        "🎧 **Ovozli xabar** - Musiqa parchasini yuboring, men taniyman (Shazam).\n"
        "🔗 **Link yuboring** - Instagram, YouTube, TikTok va SoundCloud havolalarini yuklayman.\n\n"
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
        "1. **Qidiruv:** Musiqa nomi yoki ijrochini yozib yuboring (masalan: `Yulduz Usmonova`)\n"
        "2. **Link orqali:** Instagram, YouTube, TikTok yoki SoundCloud havolasini yuboring.\n"
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
        
        # YouTube linklaridan ID ajratib olish (kuchaytirilgan regex)
        video_id = None
        if "youtube.com" in url or "youtu.be" in url:
            import re
            match = re.search(r"(?:v=|embed\/|watch\?v=|ytscreen\/|shorts\/|\/)([0-9A-Za-z_-]{11})", url)
            if match:
                video_id = match.group(1)
        
        # Keshni URL yoki video_id bo'yicha tekshirish
        cached_data = db_cache.get_file_id(url)
        if not cached_data and video_id:
            cached_data = db_cache.get_file_id(video_id)
            
        if cached_data:
            try:
                await sent_message.edit_text(f"⚡️ **{cached_data.get('title', 'Musiqa')}** keshdan yuborilmoqda...")
                await message.answer_audio(
                    cached_data['file_id'],
                    caption=f"✅ **{cached_data.get('title', 'Musiqa')}**\n\n⚡️ Tezkor yuklash (keshdan)\n🤖 @{BOT_USERNAME}",
                    parse_mode="Markdown"
                )
                await sent_message.delete()
                return
            except Exception as e:
                logger.warning(f"Link keshidan yuborishda xato: {e}")

        result = await download_media(url, 'audio')
        if result['success']:
            file_path = result['file_path']
            # Fayl hajmini tekshirish
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE_BYTES:
                await sent_message.edit_text(f"⚠️ **Fayl juda katta!** ({file_size / (1024*1024):.1f} MB)\nTelegram botlar orqali faqat 50MB gacha bo'lgan fayllarni yuborish mumkin.")
                if os.path.exists(file_path): os.remove(file_path)
                return

            audio = FSInputFile(file_path)
            caption = f"🎵 **{result['title']}**\n\n📥 @{BOT_USERNAME} orqali yuklandi"
            msg = await message.answer_audio(audio, caption=caption, parse_mode="Markdown")
            
            # Keshga saqlash (URL va ID bo'yicha)
            if msg.audio:
                db_cache.set_file_id(url, msg.audio.file_id, result['title'])
                final_id = video_id or result.get('id')
                if final_id:
                    db_cache.set_file_id(final_id, msg.audio.file_id, result['title'])
                
            await sent_message.delete()
            if os.path.exists(result['file_path']): os.remove(result['file_path'])
        else:
            await sent_message.edit_text(f"❌ **Xatolik:** {result['error']}")
        return

    # Aqlli qidiruv
    query = message.text.strip()
    if len(query) < 3 or query.startswith('/') or query.startswith('.'):
        return

    sent_message = await message.answer(f"🔍 **'{query}'** qidirilmoqda...", parse_mode="Markdown")
    results = await get_search_results(query, 10)
    
    if not results:
        await sent_message.edit_text(f"😔 **'{query}'** bo'yicha hech qanday musiqa topilmadi. Iltimos, nomini tekshirib qayta yozing.")
        return

    user_searches[message.from_user.id] = results
    
    response_text = f"✨ **'{query}'** bo'yicha eng yaxshi natijalar:\n\n"
    for i, res in enumerate(results):
        duration = format_duration(res['duration'])
        # Ikonka allaqachon res['title'] ichida bor
        response_text += f"{i+1}. {res['title']} ({duration})\n"
    
    response_text += "\n📥 **Yuklab olish uchun raqamni tanlang:**"
    
    await sent_message.edit_text(
        response_text, 
        reply_markup=get_search_keyboard(len(results)),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("dl_idx_"))
async def process_selection(callback: CallbackQuery, bot: Bot):
    idx = int(callback.data.replace("dl_idx_", ""))
    user_id = callback.from_user.id
    
    if user_id not in user_searches or idx >= len(user_searches[user_id]):
        await callback.answer("❌ Qidiruv natijasi muddati o'tgan. Iltimos, qaytadan qidiring.", show_alert=True)
        return

    selected = user_searches[user_id][idx]
    video_id = selected.get('id')
    url = selected.get('url')
    
    # Keshni tekshirish (URL yoki video_id bo'yicha)
    cached_data = None
    if url:
        cached_data = db_cache.get_file_id(url)
    if not cached_data and video_id:
        cached_data = db_cache.get_file_id(video_id)
        
    if cached_data:
        try:
            await callback.message.edit_text(f"⚡️ **{selected['title']}** keshdan yuborilmoqda...")
            await callback.message.answer_audio(
                cached_data['file_id'], 
                caption=f"✅ **{selected['title']}**\n\n⚡️ Tezkor yuklash (keshdan)\n🤖 @{BOT_USERNAME}",
                parse_mode="Markdown"
            )
            await callback.message.delete()
            return
        except Exception as e:
            logger.warning(f"Keshdan yuborishda xato (ehtimol file_id eskirgan): {e}")
            # Agar keshdan yuborish o'xshamasa, oddiy yuklashga o'tadi

    await callback.message.edit_text(f"⏳ **{selected['title']}** yuklanmoqda...", parse_mode="Markdown")
    
    result = await download_audio_by_url(selected['url'])
    if result['success']:
        file_path = result['file_path']
        # Fayl hajmini tekshirish
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE_BYTES:
            await callback.message.edit_text(f"⚠️ **Fayl juda katta!** ({file_size / (1024*1024):.1f} MB)\nTelegram botlar orqali faqat 50MB gacha bo'lgan fayllarni yuborish mumkin.")
            if os.path.exists(file_path): os.remove(file_path)
            return

        audio = FSInputFile(file_path)
        caption = f"✅ **{selected['title']}**\n\n🤖 @{BOT_USERNAME}"
        msg = await callback.message.answer_audio(audio, caption=caption, parse_mode="Markdown")
        
        # Kelajak uchun keshga saqlash (URL va ID bo'yicha)
        if msg.audio:
            if selected.get('url'):
                db_cache.set_file_id(selected['url'], msg.audio.file_id, selected['title'])
            if video_id:
                db_cache.set_file_id(video_id, msg.audio.file_id, selected['title'])
            
        await callback.message.delete()
        if os.path.exists(result['file_path']): os.remove(result['file_path'])
    else:
        err_msg = result.get('error', "Noma'lum")
        await callback.message.edit_text(f"❌ Xatolik yuz berdi: {err_msg}")

@router.callback_query(F.data == "cancel_search")
async def cancel_search(callback: CallbackQuery):
    if callback.from_user.id in user_searches:
        del user_searches[callback.from_user.id]
    await callback.message.delete()
    await callback.answer("Qidiruv bekor qilindi.")

@router.message(F.voice | F.audio | F.video | F.video_note)
async def handle_audio(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer("⚠️ Avval kanalga obuna bo'ling!", reply_markup=get_sub_markup())
        return

    sent_message = await message.answer("🎧 **Musiqa tanilmoqda (Shazam)...**", parse_mode="Markdown")
    
    if message.voice:
        file_id = message.voice.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    else:
        return

    file = await bot.get_file(file_id)
    # Fayl kengaytmasini aniqlash
    ext = file.file_path.split('.')[-1] if '.' in file.file_path else 'ogg'
    file_path = os.path.join(DOWNLOADS_DIR, f"{uuid.uuid4()}.{ext}")
    await bot.download_file(file.file_path, file_path)

    shazam_result = await recognize_song(file_path)
    if os.path.exists(file_path): os.remove(file_path)

    if shazam_result['status'] == 'success':
        title = shazam_result['title']
        subtitle = shazam_result['artist']
        query = f"{title} {subtitle}"
        
        await sent_message.edit_text(f"✅ **Topildi!**\n\n🎼 **Nomi:** {title}\n👤 **Ijrochi:** {subtitle}\n\n🔍 Eng yaxshi versiyalarni qidiryapman...")
        
        results = await get_search_results(query, 10)
        if not results:
            await sent_message.edit_text(f"😔 Musiqani topdim ({title}), lekin yuklash uchun manba topilmadi.")
            return

        user_searches[message.from_user.id] = results
        
        response_text = f"✅ **Musiqa tanildi:**\n🎼 **{title}** — {subtitle}\n\n📥 **Yuklash uchun versiyani tanlang:**\n"
        for i, res in enumerate(results):
            duration = format_duration(res['duration'])
            response_text += f"{i+1}. {res['title']} ({duration})\n"
        
        await sent_message.edit_text(
            response_text,
            reply_markup=get_search_keyboard(len(results)),
            parse_mode="Markdown"
        )
    else:
        await sent_message.edit_text("❌ **Musiqa tanilmadi.** Ovoz baland va aniqroq bo'lishiga e'tibor bering.")
