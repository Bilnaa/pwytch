from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, ValidationError

USER_ID_HEADER = "X-User-Id"
USER_NAME_HEADER = "X-User-Name"
USER_ROLE_HEADER = "X-User-Role"


class UserIdentity(BaseModel):
    id: int
    name: str
    role: str


def to_headers(user: UserIdentity) -> dict[str, str]:
    return {
        USER_ID_HEADER: str(user.id),
        USER_NAME_HEADER: user.name,
        USER_ROLE_HEADER: user.role,
    }


def get_current_user(request: Request) -> UserIdentity:
    # main has already authenticated the user: a satellite only trusts these headers
    try:
        return UserIdentity(
            id=request.headers[USER_ID_HEADER],
            name=request.headers[USER_NAME_HEADER],
            role=request.headers[USER_ROLE_HEADER],
        )
    except (KeyError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        ) from None


CurrentUser = Annotated[UserIdentity, Depends(get_current_user)]
