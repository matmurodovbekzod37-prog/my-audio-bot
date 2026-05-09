import logging
from shazamio import Shazam

logger = logging.getLogger(__name__)
shazam = Shazam()

async def recognize_song(file_path: str) -> dict:
    """
    Fayldan (mp3, mp4) musiqani taniydi va nomini qaytaradi.
    :param file_path: Yuklab olingan audio/video fayl manzili
    :return: Diktionary (success, title, artist, error)
    """
    try:
        out = await shazam.recognize(file_path)
        
        if not out.get("track"):
            return {
                "success": False,
                "error": "Musiqa topilmadi yoki bu videoda aniq musiqa yo'q."
            }
            
        track = out["track"]
        title = track.get("title", "Noma'lum musiqa")
        artist = track.get("subtitle", "Noma'lum ijrochi")
        
        return {
            "success": True,
            "title": title,
            "artist": artist,
            "full_name": f"{artist} - {title}"
        }
        
    except Exception as e:
        logger.error(f"Shazam xatoligi: {e}")
        return {
            "success": False,
            "error": str(e)
        }
