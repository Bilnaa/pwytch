"""Simulates a streamer: sends a video file to the ingest WebSocket, chunk by chunk."""

import argparse
import asyncio
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

CHUNK_SIZE = 64 * 1024


async def main(path: Path, url: str, delay: float) -> None:
    data = path.read_bytes()
    sent = 0
    try:
        async with connect(url) as ws:
            for i in range(0, len(data), CHUNK_SIZE):
                chunk = data[i : i + CHUNK_SIZE]
                await ws.send(chunk)
                sent += len(chunk)
                await asyncio.sleep(delay)
    except ConnectionClosed as exc:
        print(f"connection closed by the server ({exc.rcvd.code if exc.rcvd else '?'}) after {sent} bytes")
        return
    print(f"sent {sent} bytes to {url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="video file to send (WebM)")
    parser.add_argument("stream_id", type=int, help="live id")
    parser.add_argument(
        "--url", help="WebSocket URL (default: ws://localhost:8001/streams/{stream_id}/ingest)"
    )
    parser.add_argument(
        "--delay", type=float, default=0.1, help="pause in seconds between chunks (default: 0.1)"
    )
    args = parser.parse_args()

    url = args.url or f"ws://localhost:8001/streams/{args.stream_id}/ingest"
    asyncio.run(main(args.file, url, args.delay))
