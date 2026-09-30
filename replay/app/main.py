from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="replay")

app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "replay"}
