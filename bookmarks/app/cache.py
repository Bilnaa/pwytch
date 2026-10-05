import logging

from redis import Redis, RedisError

from app.config import settings
from app.schemas import TargetType

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

# short timeouts: if Redis is down, a route waits half a second, then reads the database
redis_client = Redis.from_url(
    settings.redis_url,
    socket_timeout=0.5,
    socket_connect_timeout=0.5,
    decode_responses=True,
)


def get_redis() -> Redis:
    return redis_client


def user_prefix(user_id: int) -> str:
    return f"bookmarks:user:{user_id}:"


def bookmark_key(user_id: int, bookmark_id: int) -> str:
    return f"{user_prefix(user_id)}bookmark:{bookmark_id}"


def list_key(
    user_id: int,
    target_type: TargetType | None,
    target_id: int | None,
    page: int,
    size: int,
) -> str:
    # every query parameter is in the key: two different lists never share an entry
    type_part = target_type.value if target_type is not None else "all"
    id_part = target_id if target_id is not None else "all"
    return f"{user_prefix(user_id)}list:{type_part}:{id_part}:{page}:{size}"


def read(redis: Redis, key: str) -> str | None:
    try:
        return redis.get(key)
    except RedisError as exc:
        logger.warning("Cache read failed for %s: %s", key, exc)
        return None


def write(redis: Redis, key: str, value: str) -> None:
    try:
        redis.set(key, value, ex=CACHE_TTL_SECONDS)
    except RedisError as exc:
        logger.warning("Cache write failed for %s: %s", key, exc)


def invalidate_user(redis: Redis, user_id: int) -> None:
    try:
        keys = list(redis.scan_iter(match=f"{user_prefix(user_id)}*"))
        if keys:
            redis.delete(*keys)
    except RedisError as exc:
        logger.warning("Cache invalidation failed for user %s: %s", user_id, exc)
