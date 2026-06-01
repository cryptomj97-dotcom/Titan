import asyncio
import pickle
from typing import Any, Callable, Optional

import redis.asyncio as aioredis


class RedisCache:
    def __init__(self, url: str = "redis://localhost:6379/0"):
        self._client = aioredis.from_url(url, decode_responses=False)

    async def get(self, key: str) -> Optional[Any]:
        raw = await self._client.get(key)
        if raw is None:
            return None
        return pickle.loads(raw)

    async def set(self, key: str, value: Any, ttl: int) -> None:
        data = pickle.dumps(value)
        await self._client.set(key, data, ex=ttl)

    async def fetch_with_cache(self, key: str, ttl: int, fetch_fn: Callable[..., Any], *args, **kwargs) -> Any:
        cached = await self.get(key)
        if cached is not None:
            return cached
        result = await asyncio.to_thread(fetch_fn, *args, **kwargs)
        await self.set(key, result, ttl)
        return result
