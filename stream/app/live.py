import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from common import topics
from common.events import StreamEnded, StreamStarted

from app import events
from app.hls import HlsPipeline, SlatePipeline, probe_size

logger = logging.getLogger(__name__)

# lives that are not over yet, connected or waiting for the streamer
lives: dict[int, "Live"] = {}

STARTED_FILE = "started.json"


@dataclass
class LiveInfo:
    streamer_id: int
    streamer_name: str
    title: str
    game: str


class Live:
    """A live can span several connections of the streamer, the slate fills the gaps."""

    def __init__(self, stream_id: int, lives_dir: Path, info: LiveInfo):
        self.stream_id = stream_id
        self.info = info
        self.output_dir = lives_dir / str(stream_id)
        self.pipeline: HlsPipeline | None = None
        self.slate: SlatePipeline | None = None
        self.grace: asyncio.TimerHandle | None = None
        self.disconnecting: asyncio.Task | None = None
        self.ending: asyncio.Task | None = None
        self.started_at: datetime | None = None
        self.size: tuple[int, int] | None = None
        self.failed = False

    @classmethod
    def create(cls, stream_id: int, lives_dir: Path, info: LiveInfo) -> "Live":
        live = cls(stream_id, lives_dir, info)
        # raises FileExistsError if this stream_id was already used: its files are a replay now
        live.output_dir.mkdir(parents=True)
        lives[stream_id] = live
        return live

    @property
    def connected(self) -> bool:
        return self.pipeline is not None

    async def connect(self) -> HlsPipeline:
        # set before any await, so a second connection sees the live as connected
        self.pipeline = HlsPipeline(self.stream_id, self.output_dir)
        if self.disconnecting:
            await self.disconnecting  # the slate may still be starting
        if self.grace:
            self.grace.cancel()
        if self.slate:
            await self.slate.close()
            self.slate = None
        await self.pipeline.start(self.size)
        if self.started_at is None:
            # only the first ffmpeg starts the live, a reconnection doesn't
            self.started_at = datetime.now(timezone.utc)
            started = StreamStarted(
                stream_id=self.stream_id, started_at=self.started_at, **asdict(self.info)
            )
            # kept on disk: after a restart it is all we have left to publish stream/ended
            try:
                (self.output_dir / STARTED_FILE).write_text(started.model_dump_json())
            except OSError as exc:
                logger.error("Live %s: %s not written: %s", self.stream_id, STARTED_FILE, exc)
            await events.publish(topics.STREAM_STARTED, started)
        return self.pipeline

    def disconnect(self, reconnect_seconds: float) -> asyncio.Task:
        # in a task so it still runs if the handler gets cancelled
        self.disconnecting = asyncio.create_task(self._disconnect(reconnect_seconds))
        return self.disconnecting

    async def _disconnect(self, reconnect_seconds: float) -> None:
        # only the last connection counts: a live that came back after a crash ends normally
        self.failed = await self.pipeline.close() != 0
        self.pipeline = None
        if self.ending:
            return
        if self.size is None:
            # the first connection chose the size, everything after it follows
            self.size = await probe_size(self.output_dir / "index0.ts")
        self.slate = SlatePipeline(self.stream_id, self.output_dir)
        await self.slate.start(self.size)
        self.grace = asyncio.get_running_loop().call_later(reconnect_seconds, self.end)

    def end(self) -> asyncio.Task:
        # a task too, so the live gets its #EXT-X-ENDLIST even if end() is called twice
        if self.ending is None:
            self.ending = asyncio.create_task(self._end())
        return self.ending

    async def _end(self) -> None:
        if self.grace:
            self.grace.cancel()
        if self.disconnecting:
            await self.disconnecting
        for pipeline in (self.pipeline, self.slate):
            if pipeline and pipeline.proc:
                await pipeline.close()
        playlist = self.output_dir / "index.m3u8"
        if playlist.exists():
            with playlist.open("a") as f:
                f.write("#EXT-X-ENDLIST\n")
        if self.started_at:
            ended_at = datetime.now(timezone.utc)
            await events.publish(
                topics.STREAM_ENDED,
                StreamEnded(
                    stream_id=self.stream_id,
                    streamer_id=self.info.streamer_id,
                    ended_at=ended_at,
                    duration_s=(ended_at - self.started_at).total_seconds(),
                    reason="error" if self.failed else "normal",
                ),
            )
        lives.pop(self.stream_id, None)


async def close_all() -> None:
    await asyncio.gather(*(live.end() for live in list(lives.values())))
