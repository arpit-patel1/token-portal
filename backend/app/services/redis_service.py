import redis.asyncio as aioredis
from typing import Optional

from app.core.config import settings

redis_client: Optional[aioredis.Redis] = None

async def get_redis_client() -> aioredis.Redis:
    """
    Returns the Redis client instance, creating it if it doesn't exist.
    """
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_CONNECTION_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client

async def close_redis_client():
    """
    Closes the Redis client connection if it exists.
    """
    global redis_client
    if redis_client:
        await redis_client.close()

# Example usage functions (to be expanded later for OTP and token caching)
async def set_key(key: str, value: str, expire_seconds: Optional[int] = None):
    r = await get_redis_client()
    await r.set(key, value, ex=expire_seconds)

async def get_key(key: str) -> Optional[str]:
    r = await get_redis_client()
    return await r.get(key)

async def delete_key(key: str):
    r = await get_redis_client()
    await r.delete(key)

# Helper for API token Redis key generation
def get_api_token_redis_key(hashed_token: str) -> str:
    """Generates a consistent Redis key for storing API token data."""
    return f"apitoken:{hashed_token}" 