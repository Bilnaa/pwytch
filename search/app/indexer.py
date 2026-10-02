import logging

from common.events import ChatMessage, StreamEnded, StreamStarted
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.text import normalize
from app.infra.models import LATEST_STREAM_ORDER, IndexedChatMessage, Stream, Streamer

logger = logging.getLogger(__name__)

SEARCH_TEXT_SEPARATOR = " | "


async def on_stream_started(session: AsyncSession, event: StreamStarted) -> None:
    stream = await _get_or_create_stream(session, event.stream_id)
    stream.streamer_id = event.streamer_id
    stream.title = event.title
    stream.game = event.game
    stream.started_at = event.started_at

    latest_stream = await session.scalar(
        select(Stream)
        .where(Stream.streamer_id == event.streamer_id, Stream.started_at.is_not(None))
        .order_by(*LATEST_STREAM_ORDER)
        .limit(1)
    )
    # Jamais null mais c'est juste pour typer correctement.
    if latest_stream is None:
        raise RuntimeError(f"stream {event.stream_id} not found after upsert")

    streamer = await session.get(Streamer, event.streamer_id)
    if streamer is None:
        streamer = Streamer(streamer_id=event.streamer_id)
        session.add(streamer)
    if latest_stream.stream_id == event.stream_id:
        streamer.streamer_name = event.streamer_name
    streamer.search_text = _build_search_text(streamer.streamer_name, latest_stream)

    await session.commit()


async def on_stream_ended(session: AsyncSession, event: StreamEnded) -> None:
    stream = await session.get(Stream, event.stream_id)
    if stream is None:
        stream = Stream(stream_id=event.stream_id, streamer_id=event.streamer_id)
        session.add(stream)
    # Un stream existant garde son streamer : changer de propriétaire sans recalculer
    # search_text laisserait l'index incohérent.
    stream.ended_at = event.ended_at

    await session.commit()


async def on_chat_message(session: AsyncSession, event: ChatMessage) -> None:
    stored_message = await session.get(IndexedChatMessage, event.message_id)
    if stored_message is not None:
        # Premier event gagne. sent_at n'est pas comparé : SQLite le relit sans fuseau.
        if (
            stored_message.stream_id != event.stream_id
            or stored_message.author_id != event.author_id
            or stored_message.content != event.content
        ):
            logger.warning(
                "Ignoring divergent duplicate of chat message %s", event.message_id
            )
        return

    session.add(
        IndexedChatMessage(
            message_id=event.message_id,
            stream_id=event.stream_id,
            author_id=event.author_id,
            author_name=event.author_name,
            content=event.content,
            search_text=normalize(event.content),
            sent_at=event.sent_at,
        )
    )
    await session.commit()


async def _get_or_create_stream(session: AsyncSession, stream_id: int) -> Stream:
    stream = await session.get(Stream, stream_id)
    if stream is None:
        stream = Stream(stream_id=stream_id)
        session.add(stream)
    return stream


def _build_search_text(streamer_name: str, latest_stream: Stream) -> str:
    # Le séparateur empêche une requête de correspondre à cheval sur deux champs.
    fields = [streamer_name, latest_stream.title or "", latest_stream.game or ""]
    return normalize(SEARCH_TEXT_SEPARATOR.join(fields))
