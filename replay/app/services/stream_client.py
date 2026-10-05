import logging

import httpx

logger = logging.getLogger(__name__)


async def playlist_is_missing(stream_client: httpx.AsyncClient, stream_id: int) -> bool:
    """Vrai seulement si stream répond 404 : dans le doute, le replay est gardé."""
    try:
        response = await stream_client.head(f"/lives/{stream_id}/index.m3u8")
    except httpx.HTTPError as exc:
        logger.warning(
            "Playlist of live %s not checked, replay kept: %s", stream_id, exc
        )
        return False
    if response.status_code == 404:
        return True
    if not response.is_success:
        logger.warning(
            "Playlist of live %s not checked (HTTP %s), replay kept",
            stream_id,
            response.status_code,
        )
    return False
