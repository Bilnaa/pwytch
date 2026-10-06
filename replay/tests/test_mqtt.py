import asyncio

import pytest
from common.topics import STREAM_ENDED, STREAM_STARTED

from app.consumers.mqtt import create_mqtt_client
from app.core.config import Settings
from app.models import Mp4Status
from tests.factories import make_ended, make_started, reload, write_playlist


@pytest.mark.anyio
async def test_events_received_on_the_topics_create_the_replay_and_convert_it(
    session, session_factory, lives_dir, converter, fake_ffmpeg
):
    write_playlist(lives_dir, 42)
    app_settings = Settings(_env_file=None, lives_dir=lives_dir)
    mqtt = create_mqtt_client(app_settings, session_factory, converter)

    await mqtt.handle(STREAM_STARTED, make_started().model_dump_json())
    await mqtt.handle(STREAM_ENDED, make_ended(reason="error").model_dump_json())
    await asyncio.gather(*converter.tasks)

    stored_replay = await reload(session, 42)
    assert stored_replay.title == "Speedrun Any%"
    assert stored_replay.ended_at is not None
    assert stored_replay.mp4_status is Mp4Status.READY
