import asyncio
import logging
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Mp4Status
from app.repositories.replay_repository import finish_conversion, reset_processing

logger = logging.getLogger(__name__)

# Fin de stderr gardée dans le log : ffmpeg écrit l'erreur utile en dernier.
STDERR_TAIL_CHARS = 2000


class Mp4Converter:
    """Convertit la playlist HLS d'un live terminé en .mp4, sans réencoder."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        stream_url: str,
        replays_dir: Path,
        timeout_s: float,
    ):
        self.session_factory = session_factory
        self.stream_url = stream_url
        self.replays_dir = replays_dir
        self.timeout_s = timeout_s

    def mp4_path(self, stream_id: int) -> Path:
        return self.replays_dir / f"{stream_id}.mp4"

    def part_path(self, stream_id: int) -> Path:
        # Fichier en cours d'écriture : jamais servi, renommé seulement en cas de succès.
        return self.replays_dir / f"{stream_id}.mp4.part"

    def ffmpeg_args(self, stream_id: int) -> list[str]:
        return [
            "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
            "-i", f"{self.stream_url}/lives/{stream_id}/index.m3u8",
            "-c", "copy", "-f", "mp4", str(self.part_path(stream_id)),
        ]  # fmt: skip

    async def convert(self, stream_id: int) -> None:
        """Tâche de fond : ne lève jamais.

        Une exception y finirait en « Exception in ASGI application », sans contexte.
        """
        try:
            status = await self._produce_mp4(stream_id)
            async with self.session_factory() as session:
                written = await finish_conversion(session, stream_id, status)
            if not written:
                logger.warning(
                    "Replay %s was reset during its conversion, %s result not written",
                    stream_id,
                    status,
                )
        except Exception:
            # Statut resté en processing : le prochain démarrage le remet à none.
            logger.exception("Conversion of replay %s could not be finished", stream_id)

    async def reset_interrupted(self) -> None:
        """Au démarrage : un arrêt pendant ffmpeg laisse des .part et des lignes « processing ».

        Suppose un seul process replay : il remet à zéro toutes les conversions, y compris
        celles qu'un autre process ferait tourner. replay tourne déjà en une seule instance
        à cause de son client_id MQTT fixe (voir « Dettes connues » du README).
        """
        self.replays_dir.mkdir(parents=True, exist_ok=True)
        for part_path in self.replays_dir.glob("*.mp4.part"):
            part_path.unlink(missing_ok=True)
        try:
            async with self.session_factory() as session:
                reset_count = await reset_processing(session)
        # Même règle que try_init_db : une base coupée n'empêche pas le service de démarrer.
        except (SQLAlchemyError, OSError) as exc:
            logger.warning("Interrupted conversions not reset, database unavailable: %s", exc)
            return
        if reset_count:
            logger.warning("%d interrupted conversions reset to none", reset_count)

    async def _produce_mp4(self, stream_id: int) -> Mp4Status:
        part_path = self.part_path(stream_id)
        try:
            process = await asyncio.create_subprocess_exec(
                *self.ffmpeg_args(stream_id),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            logger.error("ffmpeg could not start for replay %s: %s", stream_id, exc)
            return Mp4Status.FAILED
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), self.timeout_s)
        except TimeoutError:
            logger.error("ffmpeg timed out after %s s for replay %s", self.timeout_s, stream_id)
            return Mp4Status.FAILED
        finally:
            # Délai dépassé ou tâche annulée (arrêt du service) : ffmpeg ne reste pas orphelin.
            if process.returncode is None:
                process.kill()
                await process.wait()
                part_path.unlink(missing_ok=True)
        if process.returncode != 0:
            part_path.unlink(missing_ok=True)
            logger.error(
                "ffmpeg failed for replay %s (exit code %s): %s",
                stream_id,
                process.returncode,
                stderr.decode(errors="replace")[-STDERR_TAIL_CHARS:],
            )
            return Mp4Status.FAILED
        part_path.replace(self.mp4_path(stream_id))
        return Mp4Status.READY

