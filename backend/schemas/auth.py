
from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    roll_number: str | None = Field(default=None, max_length=30)
    building_id: str | None = Field(default=None, max_length=50)


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    token: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendOTPRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
