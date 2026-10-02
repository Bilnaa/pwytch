import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import aiomqtt
from pydantic import ValidationError

from common.events import BaseEvent

logger = logging.getLogger(__name__)

QOS = 1


class NotConnectedError(Exception):
    pass


@dataclass
class Subscription[E: BaseEvent]:
    model: type[E]
    handler: Callable[[E], Awaitable[None]]


class MqttClient:
    """Asynchronous MQTT client that reconnects by itself.

    Use `start()` when the service starts and `stop()` when it stops. The subscriptions
    are sent again to the broker after every reconnection.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        client_id: str | None = None,
        reconnect_seconds: float = 5,
        dedup_size: int = 1000,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.reconnect_seconds = reconnect_seconds
        self.dedup_size = dedup_size
        self._subscriptions: dict[str, Subscription] = {}
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._client: aiomqtt.Client | None = None
        self._task: asyncio.Task | None = None

    @property
    def connected(self) -> bool:
        return self._client is not None

    def subscribe[E: BaseEvent](
        self, topic: str, model: type[E], handler: Callable[[E], Awaitable[None]]
    ) -> None:
        self._subscriptions[topic] = Subscription(model, handler)

    async def publish(self, topic: str, event: BaseEvent) -> None:
        if self._client is None:
            raise NotConnectedError("Not connected to the MQTT broker")
        try:
            await self._client.publish(topic, event.model_dump_json(), qos=QOS)
        except aiomqtt.MqttError as exc:
            raise NotConnectedError("Could not publish to the MQTT broker") from exc

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                async with aiomqtt.Client(
                    self.host, self.port, identifier=self.client_id
                ) as client:
                    self._client = client
                    for topic in self._subscriptions:
                        await client.subscribe(topic, qos=QOS)
                    logger.info("Connected to the MQTT broker %s:%s", self.host, self.port)
                    async for message in client.messages:
                        await self.handle(str(message.topic), message.payload)
            except aiomqtt.MqttError as exc:
                logger.error("MQTT connection lost, retrying: %s", exc)
            finally:
                self._client = None
            await asyncio.sleep(self.reconnect_seconds)

    async def handle(self, topic: str, payload: bytes | str) -> None:
        """Validate a received message and give it to the handler of its topic."""
        subscription = self._subscriptions.get(topic)
        if subscription is None:
            return
        try:
            event = subscription.model.model_validate_json(payload)
        except ValidationError as exc:
            logger.warning("Invalid message ignored on %s: %s", topic, exc)
            return
        if self._already_seen(event):
            return
        try:
            await subscription.handler(event)
        except Exception:
            # one bad message must not stop the consumer
            logger.exception("Handler failed for the event %s on %s", event.event_id, topic)

    def _already_seen(self, event: BaseEvent) -> bool:
        key = str(event.event_id)
        if key in self._seen:
            return True
        self._seen[key] = None
        if len(self._seen) > self.dedup_size:
            self._seen.popitem(last=False)
        return False
