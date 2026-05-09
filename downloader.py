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
        'restrictfilenames': True,  # Fayl nomida muammo bo'lmasligi uchun
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
            # mp4 ga birlashtirish
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

async def search_and_download_audio(query: str) -> dict:
    """
    Qo'shiq nomini izlab audio yuklab oladi.
    Avval YouTube, keyin SoundCloud dan qidiradi.
    """
    return await asyncio.to_thread(_search_download_sync, query)

def _make_ydl_opts(outtmpl: str) -> dict:
    opts = {
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': False,
        'playlistend': 1,
        'socket_timeout': 30,
    }
    cookiefile = _get_cookiefile()
    if cookiefile:
        opts['cookiefile'] = cookiefile
    js_runtime = _get_js_runtime()
    if js_runtime:
        opts['js_runtimes'] = js_runtime
    return opts

def _extract_first_entry(info: dict):
    """entries ro'yxatidan birinchi elementni oladi yoki None qaytaradi."""
    if not info:
        return None
    if 'entries' in info:
        entries = list(info['entries'])
        return entries[0] if entries else None
    return info

def _get_filepath(ydl, info: dict) -> str:
    filename = ydl.prepare_filename(info)
    base, _ = os.path.splitext(filename)
    mp3_path = base + '.mp3'
    if os.path.exists(mp3_path):
        return mp3_path
    return filename

def _search_download_sync(query: str) -> dict:
    outtmpl = os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s')
    ydl_opts = _make_ydl_opts(outtmpl)

    sources = [
        f"ytsearch1:{query}",
        f"scsearch1:{query}",
    ]

    for source in sources:
        try:
            logger.info(f"Izlanmoqda: {source}")
            with YoutubeDL(ydl_opts) as ydl:
                raw = ydl.extract_info(source, download=True)
                info = _extract_first_entry(raw)
                if not info:
                    logger.warning(f"{source} dan natija topilmadi, keyingisi...")
                    continue
                filepath = _get_filepath(ydl, info)
                return {
                    'success': True,
                    'file_path': filepath,
                    'title': info.get('title', "Noma'lum musiqa"),
                }
        except Exception as e:
            logger.warning(f"{source} xatolik: {e} — keyingi manbaga o'tilmoqda...")
            continue

    return {
        'success': False,
        'error': "Musiqa hech bir manbadan topilmadi. Keyinroq qayta urinib ko'ring."
    }
