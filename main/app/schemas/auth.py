from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$", examples=["john_doe"]
    )
    password: str = Field(min_length=8, examples=["MyPassword123"])
