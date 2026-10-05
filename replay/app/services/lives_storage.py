import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def playlist_path(lives_dir: Path, stream_id: int) -> Path:
    return lives_dir / str(stream_id) / "index.m3u8"


def playlist_is_missing(lives_dir: Path, stream_id: int) -> bool:
    """Vrai seulement si la playlist est absente : dans le doute, le replay est gardé."""
    if not lives_dir.is_dir():
        logger.warning(
            "Playlist of live %s not checked, lives dir %s not found, replay kept",
            stream_id,
            lives_dir,
        )
        return False
    try:
        playlist_path(lives_dir, stream_id).stat()
    except FileNotFoundError:
        return True
    except OSError as exc:
        logger.warning("Playlist of live %s not checked, replay kept: %s", stream_id, exc)
    return False
