import pytest
from common.topics import STREAM_ENDED, STREAM_STARTED

from app.consumers.mqtt import create_mqtt_client
from app.core.config import Settings
from tests.factories import make_ended, make_started, reload, write_playlist


@pytest.mark.anyio
async def test_events_received_on_the_topics_create_the_replay(session, session_factory, lives_dir):
    write_playlist(lives_dir, 42)
    mqtt = create_mqtt_client(Settings(_env_file=None, lives_dir=lives_dir), session_factory)

    await mqtt.handle(STREAM_STARTED, make_started().model_dump_json())
    await mqtt.handle(STREAM_ENDED, make_ended(reason="error").model_dump_json())

    stored_replay = await reload(session, 42)
    assert stored_replay.title == "Speedrun Any%"
    assert stored_replay.ended_at is not None
