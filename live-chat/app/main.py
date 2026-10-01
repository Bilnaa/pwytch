from fastapi import FastAPI

from app.routers import health, live_chat

app = FastAPI(title="live-chat")

app.include_router(health.router)
app.include_router(live_chat.router)

@app.get("/")
def root():
    return {"service": "live-chat"}
