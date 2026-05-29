import asyncio
import os
import logging
from pathlib import Path
from yt_dlp import YoutubeDL
from config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# Agar cookies.txt fayli mavjud bo'lsa, yt-dlp ga ulash
COOKIES_FILE = Path(__file__).parent / 'cookies.txt'

def _find_node() -> str | None:
    """Node.js bajariladigan faylini topadi."""
    import shutil
    # PATH dan qidirish
    node = shutil.which('node')
    if node:
        return node
    # Windows standart o'rnatish joylari
    candidates = [
        r'C:\Program Files\nodejs\node.exe',
        r'C:\Program Files (x86)\nodejs\node.exe',
        str(Path.home() / 'AppData' / 'Roaming' / 'npm' / 'node.exe'),
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None

def _get_cookiefile() -> str | None:
    if COOKIES_FILE.exists():
        logger.info(f"Cookies ishlatilmoqda: {COOKIES_FILE}")
        return str(COOKIES_FILE)
    return None

def _get_js_runtime() -> dict | None:
    node = _find_node()
    if node:
        # yt-dlp expects a dict: {runtime_name: {config_dict}}
        return {'node': {'path': node}}
    return None

async def download_media(url: str, format_type: str = 'audio') -> dict:
    """
    Berilgan URL dan media (audio yoki video) yuklab oladi.
    format_type: 'audio' yoki 'video'
    """
    return await asyncio.to_thread(_download_sync, url, format_type)

def _download_sync(url: str, format_type: str) -> dict:
    # Saqlash manzili va fayl nomi shabloni
    outtmpl = os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s')
    
    # URL ga qarab referer tanlash
    referer = "https://www.google.com/"
    if "soundcloud.com" in url:
        referer = "https://soundcloud.com/"
    elif "instagram.com" in url:
        referer = "https://www.instagram.com/"

    cookiefile = _get_cookiefile()
    # Bazaviy sozlamalar
    ydl_opts = {
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'cachedir': False,
        'no_mtime': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'referer': referer,
        'extractor_args': {
            'youtube': {
                # Bir nechta mobil va veb mijozlarni sinab ko'rish orqali blokni aylanib o'tish
                'player_client': ['ios', 'android', 'web_safari', 'mweb'],
            }
        },
    }
    
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    if format_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })

    js_runtime = _get_js_runtime()
    if js_runtime:
        ydl_opts['js_runtimes'] = js_runtime

    try:
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception as e:
                # Agar kuki bilan xato bo'lsa, kukisiz sinab ko'ramiz
                if cookiefile:
                    logger.warning(f"Kuki bilan xato ({e}), kukisiz urinib ko'ramiz...")
                    ydl_opts.pop('cookiefile', None)
                    with YoutubeDL(ydl_opts) as ydl_no_cookies:
                        info = ydl_no_cookies.extract_info(url, download=True)
                else:
                    raise e
            
            if not info:
                raise Exception("Media ma'lumotlarini olish imkoni bo'lmadi")

            # Fayl nomini aniqlash
            filename = ydl.prepare_filename(info)
            if format_type == 'audio':
                base, _ = os.path.splitext(filename)
                expected_filename = base + '.mp3'
                if os.path.exists(expected_filename):
                    filename = expected_filename
            else:
                base, _ = os.path.splitext(filename)
                expected_filename = base + '.mp4'
                if os.path.exists(expected_filename):
                    filename = expected_filename

            return {
                'success': True,
                'file_path': filename,
                'title': info.get('title', 'Noma\'lum'),
                'duration': info.get('duration', 0),
                'id': info.get('id')
            }
    except Exception as e:
        err_str = str(e)
        logger.error(f"Download error: {err_str}")
        
        # Foydalanuvchiga oqilona va yordam beruvchi xato xabari
        if "Sign in to confirm" in err_str or "confirm your age" in err_str or "403: Forbidden" in err_str:
            if "youtube.com" in url or "youtu.be" in url:
                friendly_err = (
                    "⚠️ **YouTube yuklash cheklovi (IP Blocked):**\n"
                    "YouTube ushbu havola bo'yicha yuklashni vaqtincha chekladi (bot aniqlanganligi sababli).\n\n"
                    "💡 **Nima qilish kerak?**\n"
                    "Musiqani matn ko'rinishida yozib yuboring (masalan: `Sherali Jo'rayev Karvon`) va qidiruv natijalaridan SoundCloud **Cloud (☁️)** versiyasini tanlang! SoundCloud butunlay cheklovsiz va tezkor ishlaydi."
                )
            else:
                friendly_err = (
                    "⚠️ **Yuklash cheklovi:**\n"
                    "Ushbu havoladan yuklashda bot chekloviga duch keldik.\n\n"
                    "💡 **Nima qilish kerak?**\n"
                    "Iltimos, musiqani nomi orqali oddiy matn ko'rinishida yuborib qidirib ko'ring!"
                )
        elif "Connection aborted" in err_str or "ConnectionResetError" in err_str or "10054" in err_str:
            friendly_err = (
                "⚠️ **Tarmoq cheklovi (Connection Reset):**\n"
                "Ushbu musiqa provayderi (SoundCloud) server bilan aloqani uzdi (ehtimol hududiy cheklov yoki blokirovka sababli).\n\n"
                "💡 **Nima qilish kerak?**\n"
                "Iltimos, musiqani nomi orqali qayta qidirib ko'ring va ro'yxatdan boshqa variantni (masalan, YouTube 📺 versiyasini) tanlang!"
            )
        elif "Requested format not available" in err_str:
            friendly_err = "⚠️ Ushbu formatdagi audio fayl topilmadi. Iltimos, boshqa variantni sinab ko'ring."
        elif "Video unavailable" in err_str:
            friendly_err = "⚠️ Musiqa yoki video o'chirilgan yoxud bloklangan."
        else:
            friendly_err = f"⚠️ Yuklashda muammo yuz berdi: {err_str[:100]}"
            
        return {'success': False, 'error': friendly_err}


async def get_search_results(query: str, limit: int = 10) -> list:
    """
    YouTube va SoundCloud dan parallel qidiradi va SoundCloud (Cloud ☁️) natijalarini birinchi o'ringa qo'yadi.
    Chunki Render serverida SoundCloud yuklashlari mutlaqo bepul, barqaror va cheklovsiz ishlaydi!
    """
    search_query = f"{query} audio" if len(query.split()) < 4 else query
    
    # Parallel qidiruv start
    yt_task = asyncio.to_thread(_search_provider, f"ytsearch10:{search_query}")
    sc_task = asyncio.to_thread(_search_provider, f"scsearch10:{search_query}")
    
    results_lists = await asyncio.gather(sc_task, yt_task, return_exceptions=True)
    
    # SoundCloud va YouTube natijalarini ajratib olamiz
    sc_results = results_lists[0] if isinstance(results_lists[0], list) else []
    yt_results = results_lists[1] if isinstance(results_lists[1], list) else []
    
    # Birinchi SoundCloud (☁️), keyin YouTube (📺) natijalarini joylashtiramiz
    combined_results = []
    combined_results.extend(sc_results)
    combined_results.extend(yt_results)
            
    # Dublikatlarni URL bo'yicha olib tashlash
    unique_results = []
    seen_urls = set()
    for res in combined_results:
        if res['url'] not in seen_urls:
            unique_results.append(res)
            seen_urls.add(res['url'])
            
    # Faqat limitgacha qaytarish
    return unique_results[:limit]


def _search_provider(search_str: str) -> list:
    """Yt-dlp orqali berilgan manbadan tezkor qidiruv."""
    cookiefile = _get_cookiefile()
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': True,  # JUDA MUHIM: qidiruvni tezlashtiradi
        'user_agent': user_agent,
        'noprogress': True,
    }
    
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile
        
    results = []
    prefix = "📺" if "ytsearch" in search_str else "☁️"
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_str, download=False)
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        results.append({
                            'id': entry.get('id'),
                            'title': f"{prefix} {entry.get('title')}",
                            'url': entry.get('url') or entry.get('webpage_url'),
                            'duration': entry.get('duration', 0),
                        })
        return results
    except Exception as e:
        logger.warning(f"Search provider fail ({search_str}): {e}")
        return []




async def download_audio_by_url(url: str) -> dict:
    """Aniq URL orqali audio yuklash."""
    return await asyncio.to_thread(_download_sync, url, 'audio')

async def search_and_download_audio(query: str) -> dict:
    # Bu funksiya endi faqat birinchi natijani yuklash uchun (zaxira sifatida qoladi)
    results = await get_search_results(query, 1)
    if results:
        return await download_audio_by_url(results[0]['url'])
    return {'status': 'error', 'message': 'Hech narsa topilmadi.'}
