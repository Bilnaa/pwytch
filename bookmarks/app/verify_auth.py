from typing import Annotated
from fastapi import HTTPException, Header


def verify_auth(x_user_id: Annotated[int | None, Header()] = None) -> int:
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_user_id