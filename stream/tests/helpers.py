import time
from urllib.parse import urlencode

from app import live

INFO = {"streamer_id": 1, "streamer_name": "alice", "title": "Speedrun", "game": "Celeste"}


def ingest_url(stream_id, **info):
    return f"/streams/{stream_id}/ingest?{urlencode(INFO | info)}"


def streamer(procs):
    return [p for p in procs if not p.is_slate]


def slate(procs):
    return [p for p in procs if p.is_slate]


def written(proc):
    return [c.args[0] for c in proc.stdin.write.call_args_list]


def wait_until(condition):
    deadline = time.monotonic() + 5
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)


def wait_until_finished(stream_id):
    wait_until(lambda: stream_id not in live.lives)
