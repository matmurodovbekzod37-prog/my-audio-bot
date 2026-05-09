import asyncio
import os
import logging
import shutil
from pathlib import Path
from yt_dlp import YoutubeDL
from config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# Cookies fayli manzili
COOKIES_FILE = Path(__file__).parent / 'cookies.txt'

def _get_cookiefile() -> str | None:
    if COOKIES_FILE.exists():
        return str(COOKIES_FILE)
    return None

def _find_node() -> str | None:
    node = shutil.which('node')
    if node: return node
    candidates = [r'C:\Program Files\nodejs\node.exe', r'/usr/bin/node']
    for c in candidates:
        if os.path.exists(c): return c
    return None

def _get_js_runtime() -> dict | None:
    node = _find_node()
    return {'node': {'path': node}} if node else None

def _make_ydl_opts(outtmpl: str) -> dict:
    return {
        'format': 'bestaudio/best',
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True,
        'cookiefile': _get_cookiefile(),
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        },
        'nocheckcertificate': True,
        'geo_bypass': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'js_runtimes': _get_js_runtime(),
    }

async def download_media(url: str, format_type: str = 'audio') -> dict:
    return await asyncio.to_thread(_download_sync, url, format_type)

def _download_sync(url: str, format_type: str) -> dict:
    outtmpl = os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s')
    ydl_opts = _make_ydl_opts(outtmpl)
    
    if format_type == 'video':
        ydl_opts.update({
            'format': 'bestvideo+bestaudio/best',
            'postprocessors': [], # Videoda audio ajratmaymiz
        })

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = _get_filepath(ydl, info)
            return {
                'status': 'success',
                'filepath': filepath,
                'title': info.get('title', 'Noma\'lum'),
                'duration': info.get('duration', 0)
            }
    except Exception as e:
        logger.error(f"Yuklashda xato: {e}")
        return {'status': 'error', 'message': str(e)}

def _get_filepath(ydl, info: dict) -> str:
    filename = ydl.prepare_filename(info)
    base, _ = os.path.splitext(filename)
    mp3_path = base + '.mp3'
    if os.path.exists(mp3_path): return mp3_path
    return filename

async def search_and_download_audio(query: str) -> dict:
    return await asyncio.to_thread(_search_download_sync, query)

def _search_download_sync(query: str) -> dict:
    outtmpl = os.path.join(DOWNLOADS_DIR, '%(title)s.%(ext)s')
    ydl_opts = _make_ydl_opts(outtmpl)
    sources = [f"ytsearch1:{query}", f"scsearch1:{query}"]

    for source in sources:
        try:
            with YoutubeDL(ydl_opts) as ydl:
                raw = ydl.extract_info(source, download=True)
                if 'entries' in raw and len(raw['entries']) > 0:
                    info = raw['entries'][0]
                    filepath = _get_filepath(ydl, info)
                    return {
                        'status': 'success',
                        'filepath': filepath,
                        'title': info.get('title', 'Noma\'lum'),
                        'duration': info.get('duration', 0)
                    }
        except Exception: continue
    
    return {'status': 'error', 'message': "Musiqa hech bir manbadan topilmadi."}
