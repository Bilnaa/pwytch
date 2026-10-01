import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SEGMENT_SECONDS = 4
SLATE = Path(__file__).parent.parent / "assets" / "slate.mp4"
# same size for the streamer and the slate, so the replay can still be exported with -c copy
VIDEO_FILTER = (
    "scale=1280:720:force_original_aspect_ratio=decrease,"
    "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"
)


class HlsError(Exception):
    pass


class HlsPipeline:
    input_args = ["-i", "pipe:0"]

    def __init__(self, stream_id: int, output_dir: Path):
        self.stream_id = stream_id
        self.output_dir = output_dir
        self.proc: asyncio.subprocess.Process | None = None
        self.stderr_task: asyncio.Task | None = None
        self.stderr_lines: list[str] = []
        self.closing: asyncio.Task | None = None

    async def start(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            *self.input_args,
            "-c:v", "libx264", "-preset", "veryfast", "-vf", VIDEO_FILTER,
            "-c:a", "aac", "-ar", "48000", "-ac", "2",
            "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_SECONDS})",
            "-hls_time", str(SEGMENT_SECONDS),
            "-hls_playlist_type", "event",
            # each ffmpeg adds its segments after the previous ones (with a discontinuity),
            # #EXT-X-ENDLIST is written by Live.end() once the live is really over
            "-hls_flags", "append_list+omit_endlist",
            str(self.output_dir / "index.m3u8"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
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
        # shielded so a cancelled caller can't leave a half written segment
        if self.closing is None:
            self.closing = asyncio.create_task(self._finish())
        return await asyncio.shield(self.closing)

    async def _stop_input(self) -> None:
        if not self.proc.stdin.is_closing():
            self.proc.stdin.close()
        try:
            await self.proc.stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass

    async def _finish(self) -> int:
        await self._stop_input()
        code = await self.proc.wait()
        await self.stderr_task
        if code != 0:
            logger.error(
                "ffmpeg for stream %s exited with code %s:\n%s",
                self.stream_id, code, "\n".join(self.stderr_lines),
            )
        return code


class SlatePipeline(HlsPipeline):
    """Loops the "signal lost" video while the streamer is away."""

    input_args = [
        "-re", "-stream_loop", "-1", "-i", str(SLATE),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
    ]

    async def _stop_input(self) -> None:
        # "q" makes ffmpeg finish the current segment and exit with code 0
        self.proc.stdin.write(b"q")
        await super()._stop_input()
