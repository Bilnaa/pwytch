"""Runs music channels: each folder of channels/ is a streamer that loops its tracks forever."""

import argparse
import asyncio
import random
import re
import tempfile
from pathlib import Path

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

CHUNK_SIZE = 64 * 1024
RETRY_SECONDS = 5
VIDEO = {".mp4", ".mkv", ".mov", ".webm"}
AUDIO = {".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus"}
IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
FIT = (
    "scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1"
)
# every track comes out the same way, so stream reads the whole channel as one MPEG-TS
# sent in 1080p with little loss: stream encodes it again, at its own VIDEO_HEIGHT
ENCODING = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
    "-pix_fmt", "yuv420p", "-r", "30", "-g", "60",
    "-c:a", "aac", "-ar", "48000", "-ac", "2",
]

# an audio track becomes a video: its spectrum (512x300) bent into a ring around the cover.
# Around the centre the angle gives the frequency, the distance gives the level.
# Outside the ring, a corner of the spectrum that stays black
RING = "between(hypot(X-540,Y-540),236,535)"
XMAP = f"if({RING},abs(atan2(X-540,540-Y))/PI*500,511)"
YMAP = f"if({RING},299-(hypot(X-540,Y-540)-236),0)"
MASK = "255*clip(220-hypot(X-220,Y-220),0,1)"
PLAIN = "color=c=0x14141f:s=1920x1080"
SPECTRUM = (
    "showfreqs=s=512x300:rate=30:mode=bar:fscale=log:ascale=cbrt:win_size=2048"
    ":colors=white|white,format=gray"
)
# the cover blurred behind, and round in the middle. Only its square centre is used:
# a cover kept in a file is often a square picture with bars on its sides
BACKDROP = (
    "[0:v]crop='min(iw,ih)':'min(iw,ih)',split[wide][small];"
    "[wide]scale=1920:1920,crop=1920:1080,gblur=sigma=30,"
    "eq=brightness=0.04:saturation=1.5:contrast=1.1[bg];"
    "[small]scale=440:440[square];[square][1:v]alphamerge[disc];"
    "[bg][disc]overlay=(W-w)/2:(H-h)/2"
)
VISUAL = (
    f"[0:a]{SPECTRUM}[spectrum];[spectrum][2:v][3:v]remap[ring];"
    "[ring]split[sharp][soft];[soft]gblur=sigma=9[glow];[sharp][glow]blend=all_mode=lighten[alpha];"
    "color=white:s=1080x1080:r=30,format=yuv420p[white];[white][alpha]alphamerge=shortest=1[bars];"
    "[1:v][bars]overlay=(W-w)/2:(H-h)/2:shortest=1:format=yuv420[v]"
)


async def ffmpeg(*args: str, quiet: bool = False) -> bool:
    # low priority: making a video must never slow down the channels that are live
    proc = await asyncio.create_subprocess_exec(
        "nice", "-n", "15", "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args,
        stderr=asyncio.subprocess.DEVNULL if quiet else None,
    )
    return await proc.wait() == 0


async def render(track: Path, work: Path) -> bool:
    """Makes the video of an audio track and takes its place: Lingo.wav becomes Lingo.mp4."""
    xmap, ymap, mask = work / "xmap.png", work / "ymap.png", work / "mask.png"
    for image, formula, size, pixels in (
        (xmap, XMAP, "1080x1080", "gray16le"),
        (ymap, YMAP, "1080x1080", "gray16le"),
        (mask, MASK, "440x440", "gray"),
    ):
        if not image.exists():
            source = f"color=s={size},format={pixels},geq=lum='{formula}'"
            await ffmpeg("-f", "lavfi", "-i", source, "-frames:v", "1", str(image))

    # the cover: the picture kept inside the file, the one named like the track, or cover.*
    cover = work / "cover.jpg"
    if not await ffmpeg("-i", str(track), "-an", "-frames:v", "1", str(cover), quiet=True):
        images = [f for f in track.parent.iterdir() if f.suffix.lower() in IMAGE]
        named = [f for f in images if f.stem == track.stem]
        named += [f for f in images if f.stem == "cover"]
        cover = named[0] if named else None
    backdrop = work / "backdrop.png"
    if cover:
        await ffmpeg(
            "-i", str(cover), "-i", str(mask), "-filter_complex", BACKDROP,
            "-frames:v", "1", str(backdrop),
        )
    else:
        await ffmpeg("-f", "lavfi", "-i", PLAIN, "-frames:v", "1", str(backdrop))

    # under another name until it is whole: a video that is still being written must not be played
    part = track.with_suffix(".part")
    done = await ffmpeg(
        "-i", str(track), "-loop", "1", "-framerate", "30", "-i", str(backdrop),
        "-i", str(xmap), "-i", str(ymap),
        "-filter_complex", VISUAL, "-map", "[v]", "-map", "0:a", *ENCODING, "-f", "mp4", str(part),
    )
    if done:
        part.replace(track.with_suffix(".mp4"))
        # the video holds the sound and the cover, the audio file is not needed anymore
        track.unlink()
    else:
        part.unlink(missing_ok=True)
    return done


async def convert(folder: Path, work: Path) -> None:
    """Turns the audio files of a channel into videos, one by one. Only the videos are played."""
    failed = set()
    while True:
        for track in sorted(folder.iterdir()):
            if track.suffix.lower() not in AUDIO or track in failed:
                continue
            if track.with_suffix(".mp4").exists():
                # not made here, maybe not even its video: left alone
                continue
            print(f"{folder.name}: making the video of {track.name}")
            if await render(track, work):
                print(f"{folder.name}: {track.stem}.mp4 is ready")
            else:
                print(f"{folder.name}: {track.name} could not be read, left out")
                failed.add(track)
        await asyncio.sleep(RETRY_SECONDS)


async def play(track: Path, ws) -> int:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-re", "-i", str(track), "-vf", FIT, *ENCODING, "-f", "mpegts", "pipe:1",
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
    tracks = [f for f in folder.iterdir() if f.suffix.lower() in VIDEO]
    random.shuffle(tracks)
    # a pass never starts with the track that ended the previous one
    if len(tracks) > 1 and tracks[0] == last:
        tracks.append(tracks.pop(0))
    return tracks


async def run(folder: Path, api: str, password: str, work: Path) -> None:
    name = folder.name
    if len(name) > 24:
        # main takes usernames of 30 characters at most, and "_radio" is added to the name
        print(f"{name}: folder name too long (24 characters at most), skipped")
        return
    if not any(f.suffix.lower() in VIDEO | AUDIO for f in folder.iterdir()):
        print(f"{name}: no track, skipped")
        return
    work = work / name
    work.mkdir()
    # kept in a variable: a task that nothing holds can be dropped before it ends
    _converting = asyncio.create_task(convert(folder, work))

    track = None
    while True:
        try:
            # a channel with audio files only starts when its first video is ready
            while not shuffled(folder, None):
                await asyncio.sleep(RETRY_SECONDS)
            stream_id, token = await open_session(api, name, password)
            url = f"{api.replace('http', 'ws', 1)}/streams/{stream_id}/ingest?token={token}"
            async with connect(url, max_size=None) as ws:
                print(f"{name}: live on {api}/lives/{stream_id}/index.m3u8")
                while True:
                    # the folder is read again at each pass: files can be added while it runs
                    tracks = shuffled(folder, track)
                    if not tracks:
                        raise OSError("no video left in the folder")
                    for track in tracks:
                        print(f"{name}: {track.name}")
                        if not await play(track, ws):
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
    # the pictures used to make the videos, thrown away when the script stops
    with tempfile.TemporaryDirectory() as work:
        await asyncio.gather(*(run(folder, api, password, Path(work)) for folder in folders))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "channels_dir", type=Path, nargs="?", default=Path("channels"),
        help="folder with one subfolder per channel (default: channels)",
    )
    parser.add_argument("--api", default="http://localhost:8000/api", help="URL of main's API")
    parser.add_argument(
        "--password", default="radio-password", help="password of the channel accounts"
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.channels_dir, args.api.rstrip("/"), args.password))
    except KeyboardInterrupt:
        pass
