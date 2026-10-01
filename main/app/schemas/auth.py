from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$", examples=["john_doe"]
    )
    password: str = Field(min_length=8, examples=["MyPassword123"])


class Token(BaseModel):
    access_token: str
    token_type: str = Field(examples=["bearer"])


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str = Field(examples=["john_doe"])
    display_name: str = Field(examples=["John_Doe"])
    role: str = Field(examples=["user"])
