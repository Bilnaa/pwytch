from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

USERNAME_PATTERN = r"^[a-zA-Z0-9_]{3,30}$"

# The front puts a channel at /<username>, like twitch: these names are paths of the
# front (or planned ones), a user with one of them would never get a channel page.
# Names with a "-" (go-live) are already refused by the pattern
RESERVED_USERNAMES = {
    "admin",
    "api",
    "assets",
    "bookmarks",
    "browse",
    "directory",
    "help",
    "home",
    "live",
    "lives",
    "login",
    "logout",
    "register",
    "replay",
    "replays",
    "search",
    "settings",
    "signup",
    "stats",
    "streams",
    "user",
    "users",
    "videos",
}


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3, max_length=30, pattern=USERNAME_PATTERN, examples=["john_doe"]
    )
    password: str = Field(min_length=8, examples=["MyPassword123"])

    @field_validator("username")
    @classmethod
    def not_reserved(cls, username: str) -> str:
        # usernames are stored in lowercase, so Login is refused too
        if username.lower() in RESERVED_USERNAMES:
            # not a ValueError: pydantic would add "Value error, " before the message
            raise PydanticCustomError("username_reserved", "This username is reserved")
        return username


class Token(BaseModel):
    access_token: str
    token_type: str = Field(examples=["bearer"])


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str = Field(examples=["john_doe"])
    display_name: str = Field(examples=["John_Doe"])
    role: str = Field(examples=["user"])
