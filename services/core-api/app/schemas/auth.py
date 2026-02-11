from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str
    role: str = "ved_specialist"
    company_id: str | None = None


class PublicRegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    full_name: str
    phone: str | None = None
    company_name: str | None = None
