from common import topics
from common.events import StreamEnded, StreamStarted
from common.mqtt import MqttClient

from app.config import mqtt_settings
from app.services import streams as streams_service


def create_mqtt_client() -> MqttClient:
    mqtt = MqttClient(mqtt_settings.mqtt_host, mqtt_settings.mqtt_port, client_id="main")
    mqtt.subscribe(topics.STREAM_STARTED, StreamStarted, streams_service.on_stream_started)
    mqtt.subscribe(topics.STREAM_ENDED, StreamEnded, streams_service.on_stream_ended)
    return mqtt
