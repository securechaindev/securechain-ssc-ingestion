from typing import Any

from aiocache import SimpleMemoryCache


class CacheManager:
    def __init__(self, manager: str, ttl: int = 600):
        self._cache = SimpleMemoryCache()
        self._manager = manager
        self._ttl = ttl

    async def get_cache(self, key: str) -> dict[str, Any] | None:
        return await self._cache.get(f"{self._manager}:{key}")

    async def set_cache(self, key: str, response: str) -> None:
        await self._cache.set(f"{self._manager}:{key}", response, ttl=self._ttl)

    async def clear_cache(self, key: str) -> None:
        await self._cache.clear()
