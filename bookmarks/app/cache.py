import logging

from redis import Redis, RedisError
from redis.backoff import NoBackoff
from redis.retry import Retry

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
    retry=Retry(NoBackoff(), 0), 
)


def get_redis() -> Redis:
    return redis_client


def user_prefix(user_id: int) -> str:
    return f"bookmarks:user:{user_id}:"


def version_key(user_id: int) -> str:
    return f"{user_prefix(user_id)}version"


def bookmark_key(user_id: int, version: int, bookmark_id: int) -> str:
    return f"{user_prefix(user_id)}v{version}:bookmark:{bookmark_id}"


def list_key(
    user_id: int,
    version: int,
    target_type: TargetType | None,
    target_id: int | None,
    page: int,
    size: int,
) -> str:
    # every query parameter is in the key: two different lists never share an entry
    type_part = target_type.value if target_type is not None else "all"
    id_part = target_id if target_id is not None else "all"
    return f"{user_prefix(user_id)}v{version}:list:{type_part}:{id_part}:{page}:{size}"


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


def get_version(redis: Redis, user_id: int) -> int | None:
    """Current cache version of the user, or None if Redis is unavailable."""
    try:
        value = redis.get(version_key(user_id))
    except RedisError as exc:
        logger.warning("Cache version read failed for user %s: %s", user_id, exc)
        return None
    return int(value) if value is not None else 0


def bump_version(redis: Redis, user_id: int) -> None:
    """Make every cached response of the user unreachable."""
    try:
        redis.incr(version_key(user_id))
    except RedisError as exc:
        logger.warning("Cache version bump failed for user %s: %s", user_id, exc)