from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session():
    async with SessionLocal() as db:
        yield db


SessionDep = Annotated[AsyncSession, Depends(get_session)]
