from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="live-chat")

app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "live-chat"}
