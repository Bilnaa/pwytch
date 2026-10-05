from common.mqtt import MqttClient
from fastapi import Request


def get_mqtt(request: Request) -> MqttClient:
    return request.app.state.mqtt