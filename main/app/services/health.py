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


async def check_satellites(clients: dict[str, httpx.AsyncClient]) -> dict[str, Status]:
    async with asyncio.TaskGroup() as group:
        tasks = {
            name: group.create_task(check_satellite(client)) for name, client in clients.items()
        }
    return {name: task.result() for name, task in tasks.items()}


def overall(statuses: list[Status]) -> Status:
    if all(status == "ok" for status in statuses):
        return "ok"
    return "degraded"


async def check_all(
    db: Session, mqtt: MqttClient, clients: dict[str, httpx.AsyncClient]
) -> Health:
    database = await asyncio.to_thread(check_database, db)
    broker = check_broker(mqtt)
    satellites_statuses = await check_satellites(clients)
    return Health(
        status=overall([database, broker, *satellites_statuses.values()]),
        database=database,
        broker=broker,
        satellites=satellites_statuses,
    )
