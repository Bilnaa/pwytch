from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="main")

app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "main"}
