from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="{{ cookiecutter.service_name }}")

app.include_router(health.router)


@app.get("/")
def root():
    return {"service": "{{ cookiecutter.service_name }}"}
