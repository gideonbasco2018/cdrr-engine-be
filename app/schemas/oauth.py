# app/schemas/oauth.py
from pydantic import BaseModel


class GoogleLoginRequest(BaseModel):
    credential: str


class GoogleLoginChallengeResponse(BaseModel):
    otp_required: bool = True
    pending_token: str
    email: str  # masked or full, your call — used so the frontend can show "OTP sent to ***@fda.gov.ph"


class VerifyOtpRequest(BaseModel):
    pending_token: str
    otp: str


class GoogleLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
