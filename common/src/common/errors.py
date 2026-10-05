from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


async def internal_error(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


def register_internal_error_handler(app: FastAPI) -> None:
    app.add_exception_handler(Exception, internal_error)
