from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.db import Base, engine
from app.routers import auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="main", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "main"}
