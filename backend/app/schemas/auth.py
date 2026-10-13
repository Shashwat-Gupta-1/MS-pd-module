from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    phone: str = Field(..., description="10-digit registered mobile number")
    password: str = Field(..., description="Account password")


class OTPVerifyRequest(BaseModel):
    phone: str = Field(..., description="10-digit mobile number")
    otp: str = Field(..., min_length=4, max_length=6, description="Received OTP")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    officer_id: str
    name: str


class OfficerCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of the officer")
    phone: str = Field(..., min_length=10, max_length=15, description="10-digit registered mobile number")
    password: str = Field(..., min_length=4, description="Login password")
    branch: Optional[str] = Field("Jaipur Central", description="Assigned branch")
    role: Optional[str] = Field("officer", description="Role: officer, admin, or underwriter")


class OfficerResponse(BaseModel):
    id: str
    name: str
    phone: str
    role: str
    branch: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

