import re
import os

def extract_urls(text: str) -> list[str]:
    """Matn ichidan barcha URL larni ajratib oladi."""
    url_pattern = re.compile(r'https?://[^\s]+')
    return url_pattern.findall(text)

def format_size(size_in_bytes: int) -> str:
    """Baytlardagi hajmni o'qishli formatga o'tkazadi (MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def clean_filename(filename: str) -> str:
    """Fayl nomidan nojo'ya belgilarni olib tashlaydi."""
    # Noto'g'ri belgilarni olib tashlash
    return re.sub(r'[\\/*?:"<>|]', "", filename)
