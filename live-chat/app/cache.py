import logging

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import redis_settings
from app.models.message_model import MessageModel

logger = logging.getLogger(__name__)

# Number of messages kept per live, the most the history route can return
CACHE_SIZE = 100

# Short timeouts: when Redis is down, the database answers instead of the viewer waiting
redis = Redis.from_url(
    redis_settings.redis_url,
    socket_timeout=redis_settings.redis_timeout_seconds,
    socket_connect_timeout=redis_settings.redis_timeout_seconds,
)


def key(stream_id: int) -> str:
    return f"live-chat:stream:{stream_id}:last"


async def read_last(stream_id: int) -> list[MessageModel] | None:
    # The cached messages oldest first, or None when the database must be read
    try:
        raw = await redis.lrange(key(stream_id), 0, -1)
        messages = [MessageModel.model_validate_json(item) for item in raw]
    except (RedisError, ValidationError) as exc:
        logger.warning("Chat cache of stream %s not read: %s", stream_id, exc)
        return None
    if not messages:
        # Absent key: never filled, or expired
        return None
    # A message saved while the cache was filled can be there twice
    unique = {message.id: message for message in messages}
    return sorted(unique.values(), key=lambda message: message.sent_at)


async def fill(stream_id: int, messages: list[MessageModel]) -> None:
    # Replaces the cache of a live with its last messages read from the database
    if not messages:
        # Redis can't store an empty list: a live without messages reads the database
        return
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(key(stream_id))
            pipe.rpush(key(stream_id), *(m.model_dump_json() for m in messages[-CACHE_SIZE:]))
            # A message saved while filling is missing from the cache: it comes back
            # with the next fill instead of being missing until the live ends
            pipe.expire(key(stream_id), redis_settings.cache_ttl_seconds)
            await pipe.execute()
    except RedisError as exc:
        logger.warning("Chat cache of stream %s not filled: %s", stream_id, exc)


async def append(message: MessageModel) -> None:
    # Adds a saved message to the cache of its live, if the cache exists
    try:
        async with redis.pipeline(transaction=True) as pipe:
            # RPUSHX: an absent key stays absent, otherwise the cache would only hold the
            # new messages and the history would miss the older ones in the database
            pipe.rpushx(key(message.stream_id), message.model_dump_json())
            pipe.ltrim(key(message.stream_id), -CACHE_SIZE, -1)
            await pipe.execute()
    except RedisError as exc:
        logger.warning("Message %s not added to the chat cache: %s", message.id, exc)
