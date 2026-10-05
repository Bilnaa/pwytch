from collections.abc import AsyncIterator
from typing import Annotated

from common.mqtt import MqttClient
from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import session_factory
from app.services.hit_service import HitPublisher


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


# Session rendue dès la fin de la route, avant les tâches de fond (publication des hits).
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


def get_mqtt(request: Request) -> MqttClient:
    """Dépendance FastAPI : le client créé par le lifespan, remplacé par un faux en test."""
    return request.app.state.mqtt


def get_hit_publisher(
    background_tasks: BackgroundTasks, mqtt: Annotated[MqttClient, Depends(get_mqtt)]
) -> HitPublisher:
    return HitPublisher(background_tasks, mqtt)


HitPublisherDep = Annotated[HitPublisher, Depends(get_hit_publisher)]
