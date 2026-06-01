import redis.asyncio as aioredis
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_redis_pool = None


async def get_redis_client():
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.ConnectionPool.from_url(REDIS_URL)
    return aioredis.Redis(connection_pool=_redis_pool)


async def close_redis():
    global _redis_pool
    if _redis_pool:
        await _redis_pool.disconnect()
