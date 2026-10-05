import re
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

USER_ID_HEADER = "X-User-Id"
USER_NAME_HEADER = "X-User-Name"
USER_ROLE_HEADER = "X-User-Role"

# pydantic alone would also accept "42.0", "+42" or "4_2"
USER_ID_PATTERN = re.compile(r"[0-9]+")
# ids are stored in postgres integer columns
MAX_USER_ID = 2**31 - 1


class UserIdentity(BaseModel):
    id: int = Field(gt=0, le=MAX_USER_ID)
    name: str = Field(min_length=1)
    role: str = Field(min_length=1)


def to_headers(user: UserIdentity) -> dict[str, str]:
    return {
        USER_ID_HEADER: str(user.id),
        USER_NAME_HEADER: user.name,
        USER_ROLE_HEADER: user.role,
    }


def get_current_user(request: Request) -> UserIdentity:
    # main has already authenticated the user: a satellite only trusts these headers
    try:
        if not USER_ID_PATTERN.fullmatch(request.headers[USER_ID_HEADER]):
            raise ValueError("X-User-Id is not a positive integer")
        return UserIdentity(
            id=request.headers[USER_ID_HEADER],
            name=request.headers[USER_NAME_HEADER],
            role=request.headers[USER_ROLE_HEADER],
        )
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        ) from None


CurrentUser = Annotated[UserIdentity, Depends(get_current_user)]
