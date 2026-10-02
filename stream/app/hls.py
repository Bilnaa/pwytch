import asyncio
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

SEGMENT_SECONDS = 4
SLATE = Path(__file__).parent.parent / "assets" / "slate.mp4"


def video_filter(height: int | None) -> str:
    if height is None:
        # first connection: the 16:9 frame that holds the source, never above VIDEO_HEIGHT
        box = f"trunc(min({settings.video_height},max(ih,iw*9/16))/2)*2"
        scale = f"scale=w='trunc(oh*16/9/2)*2':h='{box}'"
        pad = "pad=w='max(iw,trunc(ih*16/9/2)*2)':h='max(ih,trunc(iw*9/16/2)*2)'"
    else:
        # the size of the live is known: the slate and the reconnections keep it,
        # so the replay can still be exported with -c copy
        size = f"{height * 16 // 9 // 2 * 2}:{height}"
        scale, pad = f"scale={size}", f"pad={size}"
    return (
        f"{scale}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
        f"{pad}:x=(ow-iw)/2:y=(oh-ih)/2,setsar=1,fps=30"
    )


async def probe_height(segment: Path) -> int | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=height", "-of", "csv=p=0", str(segment),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        return int(out.split()[0])
    except (OSError, ValueError, IndexError):
        # no segment yet, or ffprobe is missing: the size stays unknown
        return None


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

    async def start(self, height: int | None = None) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            *self.input_args,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(settings.video_crf),
            "-vf", video_filter(height),
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
