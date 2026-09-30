from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="stream")

app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "stream"}
