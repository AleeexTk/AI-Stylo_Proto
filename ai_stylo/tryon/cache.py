import hashlib
import json
from typing import Optional

class TryOnCache:
    def __init__(self):
        self._cache = {} # In prod: Redis

    def get_key(self, avatar_url: str, outfit_id: str, scene: str = "default") -> str:
        payload = f"{avatar_url}:{outfit_id}:{scene}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, key: str) -> Optional[str]:
        return self._cache.get(key)

    def set(self, key: str, result_url: str):
        self._cache[key] = result_url
