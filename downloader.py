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
    ydl_opts = {
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': False,  # Debug uchun warninglarni ko'rish yaxshi
        'restrictfilenames': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        # Browser kabi ko'rinish uchun headers
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
        # YouTube blokirovkalarini aylanib o'tish uchun player clientlar
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
                'skip': ['dash', 'hls']
            }
        }
    }
    
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile
    
    js_runtime = _get_js_runtime()
    if js_runtime:
        ydl_opts['js_runtimes'] = js_runtime

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
        # Video formati uchun
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Fayl nomini olish
            if format_type == 'audio':
                # ydl_opts dagi ext 'mp3' ga aylanadi
                filename = ydl.prepare_filename(info)
                # FFmpegExtractAudio asl fayl nomidagi kengaytmani mp3 ga o'zgartiradi
                base, ext = os.path.splitext(filename)
                expected_filename = base + '.mp3'
                if os.path.exists(expected_filename):
                    filename = expected_filename
            else:
                filename = ydl.prepare_filename(info)
                base, _ = os.path.splitext(filename)
                # merge_output_format 'mp4' ga o'zgartirishi mumkin
                expected_filename = base + '.mp4'
                if os.path.exists(expected_filename):
                    filename = expected_filename

            return {
                'success': True,
                'file_path': filename,
                'title': info.get('title', 'Noma\'lum video'),
                'duration': info.get('duration', 0)
            }
    except Exception as e:
        logger.error(f"Yuklab olishda xatolik: {e}")
        return {
            'success': False,
            'error': str(e)
        }

async def get_search_results(query: str, limit: 10) -> list:
    """
    Qidiruv natijalarini ma'lumot ko'rinishida qaytaradi (yuklamaydi).
    """
    return await asyncio.to_thread(_get_search_results_sync, query, limit)

def _get_search_results_sync(query: str, limit: int) -> list:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
            }
        }
    }
    cookiefile = _get_cookiefile()
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile
    
    js_runtime = _get_js_runtime()
    if js_runtime:
        ydl_opts['js_runtimes'] = js_runtime

    try:
        with YoutubeDL(ydl_opts) as ydl:
            # YouTube va SoundCloud dan qidirish
            search_query = f"ytsearch{limit}:{query}"
            info = ydl.extract_info(search_query, download=False)
            
            results = []
            if 'entries' in info:
                for entry in info['entries']:
                    if not entry: continue
                    results.append({
                        'id': entry.get('id'),
                        'title': entry.get('title', 'Noma\'lum'),
                        'url': entry.get('url') or entry.get('webpage_url'),
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail'),
                    })
            return results
    except Exception as e:
        logger.error(f"Search error: {e}")
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
