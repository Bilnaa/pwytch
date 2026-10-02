"""Runs music channels: each folder of channels/ is a streamer that loops its tracks forever."""

import argparse
import asyncio
import random
import re
from pathlib import Path

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

CHUNK_SIZE = 64 * 1024
RETRY_SECONDS = 5
VIDEO = {".mp4", ".mkv", ".mov", ".webm"}
AUDIO = {".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus"}
FIT = "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"
BACKGROUND = "color=c=0x14141f:s=1920x1080:r=30"
WAVES = "showwaves=s=1920x270:mode=cline:rate=30:colors=white@0.8"
# every track comes out the same way, so stream reads the whole channel as one MPEG-TS
# sent in 1080p with little loss: stream encodes it again, at its own VIDEO_HEIGHT
OUTPUT = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-g", "60",
    "-c:a", "aac", "-ar", "48000", "-ac", "2",
    "-f", "mpegts", "pipe:1",
]


def ffmpeg_args(track: Path, cover: Path | None) -> list[str]:
    if track.suffix.lower() in VIDEO:
        return ["-re", "-i", str(track), "-vf", FIT, *OUTPUT]
    # no music video: the cover of the channel with the waveform of the track at the bottom
    if cover:
        background = ["-loop", "1", "-framerate", "30", "-i", str(cover)]
    else:
        background = ["-f", "lavfi", "-i", BACKGROUND]
    graph = f"[1:v]{FIT}[bg];[0:a]{WAVES}[waves];[bg][waves]overlay=0:H-h:shortest=1[v]"
    return [
        "-re", "-i", str(track), *background,
        "-filter_complex", graph, "-map", "[v]", "-map", "0:a", *OUTPUT,
    ]


async def play(track: Path, cover: Path | None, ws) -> int:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        *ffmpeg_args(track, cover),
        stdout=asyncio.subprocess.PIPE,
    )
    sent = 0
    try:
        while chunk := await proc.stdout.read(CHUNK_SIZE):
            await ws.send(chunk)
            sent += len(chunk)
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
    return sent


async def open_session(api: str, name: str, password: str) -> tuple[int, str]:
    username = re.sub(r"[^a-zA-Z0-9]", "_", name) + "_radio"
    async with httpx.AsyncClient(base_url=api) as client:
        # 409 if the account is already there, the login tells if the password is right
        register = await client.post(
            "/auth/register", json={"username": username, "password": password}
        )
        if register.status_code != 409:
            register.raise_for_status()
        login = await client.post("/auth/login", data={"username": username, "password": password})
        login.raise_for_status()
        token = login.json()["access_token"]

        created = await client.post(
            "/streams",
            json={"title": f"{name} radio", "game": "Music"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if created.status_code == 409:
            # the session of a previous run is still open, the channel goes on in it
            for status in ("live", "created"):
                page = await client.get("/streams", params={"status": status, "size": 100})
                page.raise_for_status()
                for stream in page.json()["items"]:
                    if stream["streamer"]["username"] == username.lower():
                        return stream["id"], token
        created.raise_for_status()
        return created.json()["id"], token


def shuffled(folder: Path, last: Path | None) -> list[Path]:
    tracks = [f for f in folder.iterdir() if f.suffix.lower() in VIDEO | AUDIO]
    random.shuffle(tracks)
    # a pass never starts with the track that ended the previous one
    if len(tracks) > 1 and tracks[0] == last:
        tracks.append(tracks.pop(0))
    return tracks


async def run(folder: Path, api: str, password: str) -> None:
    name = folder.name
    if len(name) > 24:
        # main takes usernames of 30 characters at most, and "_radio" is added to the name
        print(f"{name}: folder name too long (24 characters at most), skipped")
        return
    if not shuffled(folder, None):
        print(f"{name}: no track, skipped")
        return

    track = None
    while True:
        try:
            stream_id, token = await open_session(api, name, password)
            url = f"{api.replace('http', 'ws', 1)}/streams/{stream_id}/ingest?token={token}"
            async with connect(url, max_size=None) as ws:
                print(f"{name}: live on {api}/lives/{stream_id}/index.m3u8")
                while True:
                    # the folder is read again at each pass: files can be added while it runs
                    tracks = shuffled(folder, track)
                    if not tracks:
                        raise OSError("no track left in the folder")
                    cover = next(folder.glob("cover.*"), None)
                    for track in tracks:
                        print(f"{name}: {track.name}")
                        if not await play(track, cover, ws):
                            # ffmpeg could not read it, don't loop on it at full speed
                            await asyncio.sleep(1)
        except ConnectionClosed as exc:
            reason = f"{exc.rcvd.code} {exc.rcvd.reason}" if exc.rcvd else "no close frame"
            print(f"{name}: connection closed ({reason})")
        except (httpx.HTTPError, OSError, WebSocketException) as exc:
            print(f"{name}: {exc}")
        print(f"{name}: new try in {RETRY_SECONDS} s")
        await asyncio.sleep(RETRY_SECONDS)


async def main(channels_dir: Path, api: str, password: str) -> None:
    folders = sorted(f for f in channels_dir.iterdir() if f.is_dir())
    await asyncio.gather(*(run(folder, api, password) for folder in folders))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "channels_dir", type=Path, nargs="?", default=Path("channels"),
        help="folder with one subfolder per channel (default: channels)",
    )
    parser.add_argument("--api", default="http://localhost:8000", help="URL of main")
    parser.add_argument(
        "--password", default="radio-password", help="password of the channel accounts"
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.channels_dir, args.api.rstrip("/"), args.password))
    except KeyboardInterrupt:
        pass
