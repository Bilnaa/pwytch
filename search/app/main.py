from fastapi import FastAPI

from app.routers import health, search

app = FastAPI(title="search")

app.include_router(health.router)
app.include_router(search.router)


@app.get("/")
def root():
    return {"service": "search"}
