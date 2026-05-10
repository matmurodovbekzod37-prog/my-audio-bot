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
    
    cookiefile = _get_cookiefile()
    # Bazaviy sozlamalar
    ydl_opts = {
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'nocheckcertificate': True,
        'ignoreerrors': False, # Xatolikni tutish uchun False qilamiz
        'logtostderr': False,
        'cachedir': False,
        'check_formats': False,
        'no_mtime': True,
        'ignore_config': True,
        # Yangilangan User-Agent
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
        'extractor_args': {
            'youtube': {
                # Faqat ishonchli mijozlarni qoldiramiz
                'player_client': ['android', 'ios', 'mweb'],
                'player_skip': ['webpage'] # Ma'lumot olishda xatolikni kamaytiradi
            }
        },
        'youtube_include_dash_manifest': False,
        'youtube_include_hls_manifest': False,
    }
    
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    if format_type == 'audio':
        ydl_opts.update({
            'format': 'ba/ba*',
            'format_sort': ['abr:192', 'acodec:mp3'],
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
        
        # Foydalanuvchiga tushunarli xato xabari
        if "Sign in to confirm" in err_str:
            friendly_err = "YouTube bot ekanligimizni aniqladi. Iltimos, cookies.txt faylini yangilang."
        elif "Requested format not available" in err_str:
            friendly_err = "Ushbu formatdagi fayl topilmadi. Boshqa versiyani sinab ko'ring."
        elif "Video unavailable" in err_str:
            friendly_err = "Video o'chirilgan yoki bloklangan."
        else:
            friendly_err = f"Xatolik yuz berdi: {err_str[:100]}"
            
        return {'success': False, 'error': friendly_err}


async def get_search_results(query: str, limit: 10) -> list:
    return await asyncio.to_thread(_get_search_results_sync, query, limit)

def _get_search_results_sync(query: str, limit: int) -> list:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'ignore_config': True,
    }
    
    js_runtime = _get_js_runtime()
    if js_runtime:
        ydl_opts['js_runtimes'] = js_runtime
    
    results = []
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Faqat SoundCloud dan qidirish (Cheklovlar yo'q va barqaror)
            sc_info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
            if 'entries' in sc_info:
                for entry in sc_info['entries']:
                    if entry:
                        results.append({
                            'id': entry.get('id'),
                            'title': f"☁️ {entry.get('title')}",
                            'url': entry.get('url') or entry.get('webpage_url'),
                            'duration': entry.get('duration', 0),
                        })
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return results


async def download_audio_by_url(url: str) -> dict:
    """Aniq URL orqali audio yuklash."""
    return await asyncio.to_thread(_download_sync, url, 'audio')

async def search_and_download_audio(query: str) -> dict:
    # Bu funksiya endi faqat birinchi natijani yuklash uchun (zaxira sifatida qoladi)
    results = await get_search_results(query, 1)
    if results:
        return await download_audio_by_url(results[0]['url'])
    return {'status': 'error', 'message': 'Hech narsa topilmadi.'}
