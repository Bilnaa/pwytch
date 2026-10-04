from typing import Literal

from pydantic import BaseModel

Status = Literal["ok", "degraded", "down"]


class SatelliteHealth(BaseModel):
    status: Status


class Health(BaseModel):
    status: Status
    database: Status
    broker: Status
    satellites: dict[str, Status]
