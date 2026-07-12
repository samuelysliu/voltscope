from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=160)


class LoginRequest(BaseModel):
    account: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: str
    email_verified: bool


class RegisterResponse(BaseModel):
    user: UserOut


class VerifyEmailResponse(BaseModel):
    ok: bool
    user: UserOut


class LogoutResponse(BaseModel):
    ok: bool
