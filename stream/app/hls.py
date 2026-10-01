import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SEGMENT_SECONDS = 4

# pipelines whose ffmpeg is still running, closed by close_all() on shutdown
running: set["HlsPipeline"] = set()


class HlsError(Exception):
    pass


class HlsPipeline:
    def __init__(self, stream_id: int, lives_dir: Path):
        self.stream_id = stream_id
        self.output_dir = lives_dir / str(stream_id)
        self.proc: asyncio.subprocess.Process | None = None
        self.stderr_task: asyncio.Task | None = None
        self.stderr_lines: list[str] = []
        self.closing: asyncio.Task | None = None

    async def start(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac",
            "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_SECONDS})",
            "-hls_time", str(SEGMENT_SECONDS),
            "-hls_playlist_type", "event",
            str(self.output_dir / "index.m3u8"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        running.add(self)
        # ffmpeg hangs if nobody reads stderr
        self.stderr_task = asyncio.create_task(self._read_stderr())

    async def _read_stderr(self) -> None:
        async for line in self.proc.stderr:
            self.stderr_lines.append(line.decode(errors="replace").rstrip())

    async def write(self, chunk: bytes) -> None:
        if self.proc.returncode is not None:
            raise HlsError(f"ffmpeg exited with code {self.proc.returncode}")
        try:
            self.proc.stdin.write(chunk)
            await self.proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise HlsError("ffmpeg stopped reading its input") from exc

    async def close(self) -> int:
        # shielded so a cancelled caller can't leave the playlist without #EXT-X-ENDLIST
        if self.closing is None:
            self.closing = asyncio.create_task(self._finish())
        return await asyncio.shield(self.closing)

    async def _finish(self) -> int:
        # closing stdin makes ffmpeg write #EXT-X-ENDLIST
        if not self.proc.stdin.is_closing():
            self.proc.stdin.close()
        try:
            await self.proc.stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass
        code = await self.proc.wait()
        await self.stderr_task
        if code != 0:
            logger.error(
                "ffmpeg for stream %s exited with code %s:\n%s",
                self.stream_id, code, "\n".join(self.stderr_lines),
            )
        running.discard(self)
        return code


async def close_all() -> None:
    await asyncio.gather(*(pipeline.close() for pipeline in list(running)))
