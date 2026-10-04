import httpx
import pytest
from common.topics import STREAM_ENDED, STREAM_STARTED

from app.infra.config import Settings
from app.mqtt import create_mqtt_client
from tests.factories import make_ended, make_started, reload


@pytest.mark.anyio
async def test_events_received_on_the_topics_create_the_replay(session, session_factory):
    stream_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
        base_url="http://stream",
    )
    mqtt = create_mqtt_client(Settings(_env_file=None), session_factory, stream_client)

    await mqtt.handle(STREAM_STARTED, make_started().model_dump_json())
    await mqtt.handle(STREAM_ENDED, make_ended(reason="error").model_dump_json())

    stored_replay = await reload(session, 42)
    assert stored_replay.title == "Speedrun Any%"
    assert stored_replay.ended_at is not None

