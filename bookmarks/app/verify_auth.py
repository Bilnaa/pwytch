from typing import Annotated
from fastapi import HTTPException, Header
from fastapi import Depends


def verify_auth(user_id: Annotated[int | None, Header()] = None) -> int:
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


CurrentUserId = Annotated[int, Depends(verify_auth)]