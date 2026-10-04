import asyncio
import logging

import httpx
from common.mqtt import MqttClient
from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.schemas.health import Health, SatelliteHealth, Status
from app.services import satellites

logger = logging.getLogger(__name__)

SATELLITE_HEALTH = TypeAdapter(SatelliteHealth)


def check_database(db: Session) -> Status:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Database is down: %s", exc)
        return "down"
    return "ok"


def check_broker(mqtt: MqttClient) -> Status:
    return "ok" if mqtt.connected else "down"


async def check_satellite(client: httpx.AsyncClient) -> Status:
    try:
        response = await satellites.send(client, "GET", "/health")
        return satellites.parse(response, SATELLITE_HEALTH).status
    except satellites.SatelliteError:
        return "down"


async def check_all(
    db: Session, mqtt: MqttClient, clients: dict[str, httpx.AsyncClient]
) -> Health:
    database, *statuses = await asyncio.gather(
        asyncio.to_thread(check_database, db),
        *(check_satellite(client) for client in clients.values()),
    )
    broker = check_broker(mqtt)
    all_ok = all(status == "ok" for status in (database, broker, *statuses))
    return Health(
        status="ok" if all_ok else "degraded",
        database=database,
        broker=broker,
        satellites=dict(zip(clients, statuses)),
    )
