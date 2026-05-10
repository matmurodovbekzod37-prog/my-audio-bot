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
        'no_warnings': True,
        'restrictfilenames': True,
        'nocheckcertificate': True,
        'ignoreerrors': True, # Xatolik bo'lsa ham davom etish
        'logtostderr': False,
        'cachedir': False,
        'check_formats': False,
        'no_mtime': True,
        'ignore_config': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'referer': 'https://www.google.com/',
        'extractor_args': {
            'youtube': {
                'player_client': ['tv', 'tv_embedded', 'android', 'ios', 'web', 'mweb'],
                'skip': ['webpage']
            }
        },
        'youtube_include_dash_manifest': False,
        'youtube_include_hls_manifest': False,
    }
    
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile

    if format_type == 'audio':
        ydl_opts.update({
            'format': 'ba/ba*', # Eng ishonchli format
            'format_sort': ['abr:192', 'acodec:mp3'], # Sifat bo'yicha tartiblash
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
            # Avval ma'lumotni olish va yuklash
            info = ydl.extract_info(url, download=True)
            
            if not info:
                # Agar kuki bilan xato bo'lsa, kukisiz sinab ko'ramiz
                logger.warning("Kukisiz qayta urinish...")
                ydl_opts.pop('cookiefile', None)
                with YoutubeDL(ydl_opts) as ydl_no_cookies:
                    info = ydl_no_cookies.extract_info(url, download=True)
            
            if not info:
                raise Exception("Media ma'lumotlarini olib bo'lmadi")

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
        logger.error(f"Download error: {e}")
        return {'success': False, 'error': str(e)}

async def get_search_results(query: str, limit: 10) -> list:
    return await asyncio.to_thread(_get_search_results_sync, query, limit)

def _get_search_results_sync(query: str, limit: int) -> list:
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'ignore_config': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv', 'tv_embedded', 'android', 'ios', 'web', 'mweb'],
                'skip': ['webpage']
            }
        },
        'youtube_include_dash_manifest': False,
        'youtube_include_hls_manifest': False,
    }
    
    js_runtime = _get_js_runtime()
    if js_runtime:
        ydl_opts['js_runtimes'] = js_runtime
    
    results = []
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # YouTube dan qidirish
            yt_info = ydl.extract_info(f"ytsearch{limit//2}:{query}", download=False)
            if 'entries' in yt_info:
                for entry in yt_info['entries']:
                    if entry:
                        results.append({
                            'id': entry.get('id'),
                            'title': f"📺 {entry.get('title')}",
                            'url': entry.get('url') or entry.get('webpage_url'),
                            'duration': entry.get('duration', 0),
                        })
            
            # SoundCloud dan qidirish (Cheklovlar yo'q!)
            sc_info = ydl.extract_info(f"scsearch{limit//2}:{query}", download=False)
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
