import asyncio
from pathlib import Path


class FakeProcess:
    def __init__(self, returncode: int, stderr: bytes, hang: bool):
        self.returncode = returncode
        self.stderr = stderr
        self.hang = hang
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self.hang:
            # ffmpeg bloqué : seul le délai maximal du convertisseur l'arrête.
            await asyncio.Event().wait()
        return b"", self.stderr

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode


class FakeFfmpeg:
    """Remplace asyncio.create_subprocess_exec ; écrit le .part comme le vrai ffmpeg."""

    def __init__(self):
        self.calls: list[tuple[str, ...]] = []
        self.processes: list[FakeProcess] = []
        self.returncode = 0
        self.stderr = b""
        self.hang = False
        self.missing = False

    async def __call__(self, *args: str, **kwargs) -> FakeProcess:
        self.calls.append(args)
        if self.missing:
            raise FileNotFoundError("ffmpeg")
        Path(args[-1]).write_bytes(b"partial mp4")
        process = FakeProcess(self.returncode, self.stderr, self.hang)
        self.processes.append(process)
        return process
