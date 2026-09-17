from pydantic import BaseModel, Field


class LoginRequest(BaseModel):

    username: str

    password: str



class TokenResponse(BaseModel):

    access_token: str

    token_type: str

    role: str

    must_change_password: bool


class PasswordChangeRequest(BaseModel):

    old_password: str

    new_password: str = Field(min_length=6, max_length=128)
