import logging
from typing import Annotated
from urllib.parse import urlencode

from fastapi import Depends, Request
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)


def get_redis() -> Redis:
    return redis_client

RedisDep = Annotated[Redis, Depends(get_redis)]


CACHE_TTL_SECONDS = 5

redis_client = Redis.from_url(
    settings.redis_url,
    socket_timeout=0.5,
    socket_connect_timeout=0.5,
    decode_responses=True,
    retry=Retry(NoBackoff(), 0),
)


def cache_key(request: Request) -> str:
    query = urlencode(sorted(request.query_params.multi_items()))
    if query:
        return f"stats:{request.url.path}?{query}"
    return f"stats:{request.url.path}"


async def read(redis: Redis, key: str) -> str | None:
    try:
        return await redis.get(key)
    except RedisError as exc:
        logger.warning("Cache read failed for %s: %s", key, exc)
        return None


async def write(redis: Redis, key: str, value: str) -> None:
    try:
        await redis.set(key, value, ex=CACHE_TTL_SECONDS)
    except RedisError as exc:
        logger.warning("Cache write failed for %s: %s", key, exc)