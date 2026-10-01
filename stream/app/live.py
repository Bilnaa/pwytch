import asyncio
from pathlib import Path

from app.hls import HlsPipeline, SlatePipeline

# lives that are not over yet, connected or waiting for the streamer
lives: dict[int, "Live"] = {}


class Live:
    """A live can span several connections of the streamer, the slate fills the gaps."""

    def __init__(self, stream_id: int, lives_dir: Path):
        self.stream_id = stream_id
        self.output_dir = lives_dir / str(stream_id)
        self.pipeline: HlsPipeline | None = None
        self.slate: SlatePipeline | None = None
        self.grace: asyncio.TimerHandle | None = None
        self.disconnecting: asyncio.Task | None = None
        self.ending: asyncio.Task | None = None

    @classmethod
    def create(cls, stream_id: int, lives_dir: Path) -> "Live":
        live = cls(stream_id, lives_dir)
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
        await self.pipeline.start()
        return self.pipeline

    def disconnect(self, reconnect_seconds: float) -> asyncio.Task:
        # in a task so it still runs if the handler gets cancelled
        self.disconnecting = asyncio.create_task(self._disconnect(reconnect_seconds))
        return self.disconnecting

    async def _disconnect(self, reconnect_seconds: float) -> None:
        await self.pipeline.close()
        self.pipeline = None
        if self.ending:
            return
        self.slate = SlatePipeline(self.stream_id, self.output_dir)
        await self.slate.start()
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
        lives.pop(self.stream_id, None)


async def close_all() -> None:
    await asyncio.gather(*(live.end() for live in list(lives.values())))
