# app/api/routes/oauth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.core.database import get_db
from app.core.security import create_access_token, decode_pending_token
from app.core.config import settings
from app.core.email import send_email
from app.crud import oauth as crud_user
from app.schemas.oauth import (
    GoogleLoginRequest,
    GoogleLoginChallengeResponse,
    VerifyOtpRequest,
    GoogleLoginResponse,
)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])


@router.post("/google", response_model=GoogleLoginChallengeResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token"
        )

    if idinfo.get("aud") != settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token audience mismatch"
        )

    email = idinfo.get("email")
    if not email or not idinfo.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email not verified",
        )

    google_sub = idinfo["sub"]
    user = crud_user.get_by_oauth_sub(db, oauth_sub=google_sub)

    if not user:
        user = crud_user.get_by_email(db, email=email)
        if user and not user.oauth_sub:
            user.oauth_provider = "google"
            user.oauth_sub = google_sub
            db.commit()
            db.refresh(user)

    if not user:
        user = crud_user.create_oauth_user(
            db,
            email=email,
            first_name=idinfo.get("given_name", ""),
            surname=idinfo.get("family_name", ""),
            oauth_provider="google",
            oauth_sub=google_sub,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )

    plaintext_otp, pending_token = crud_user.create_otp_challenge(db, user)

    send_email(
        to=user.email,
        subject="Your CDRR sign-in code",
        body=f"Your one-time code is {plaintext_otp}. It expires in 5 minutes.",
    )

    return GoogleLoginChallengeResponse(
        pending_token=pending_token,
        email=user.email,
    )


@router.post("/google/verify-otp", response_model=GoogleLoginResponse)
def verify_google_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    try:
        claims = decode_pending_token(payload.pending_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign-in session expired, please try again",
        )

    user_id = int(claims["sub"])
    otp_id = claims["otp_id"]

    try:
        user = crud_user.verify_otp_challenge(
            db, otp_id=otp_id, user_id=user_id, otp=payload.otp
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role.value}
    )
    return GoogleLoginResponse(access_token=access_token, token_type="bearer")
