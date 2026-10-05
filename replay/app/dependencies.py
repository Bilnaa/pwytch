from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import session_factory
from app.services.conversion_service import Mp4Converter


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


# Session rendue dès la fin de la route, avant les éventuelles tâches de fond.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]


def get_converter(request: Request) -> Mp4Converter:
    """Dépendance FastAPI : le convertisseur créé par le lifespan, remplacé en test."""
    return request.app.state.converter


ConverterDep = Annotated[Mp4Converter, Depends(get_converter)]
