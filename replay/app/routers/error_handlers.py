from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.exceptions import ConversionFailed, ReplayNotFound


def register_error_handlers(app: FastAPI) -> None:
    """Traduit les exceptions métier en réponses HTTP (mêmes codes et detail qu'avant)."""

    @app.exception_handler(ReplayNotFound)
    async def replay_not_found(request: Request, exc: ReplayNotFound) -> JSONResponse:
        return JSONResponse({"detail": "Replay not found"}, status_code=404)

    @app.exception_handler(ConversionFailed)
    async def conversion_failed(request: Request, exc: ConversionFailed) -> JSONResponse:
        return JSONResponse({"detail": "Conversion failed, try again"}, status_code=500)
