import json
import os
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, filename="file_cache.json"):
        self.filename = filename
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Keshni yuklashda xato: {e}")
                return {}
        return {}

    def _save_cache(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Keshni saqlashda xato: {e}")

    def get_file_id(self, key):
        """key: odatda youtube video_id bo'ladi"""
        return self.cache.get(key)

    def set_file_id(self, key, file_id, title=None):
        self.cache[key] = {
            'file_id': file_id,
            'title': title
        }
        self._save_cache()

# Singleton instance
db_cache = CacheManager()
