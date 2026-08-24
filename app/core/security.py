# app/core/security.py
"""
Security utilities
Password hashing and JWT token management
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

# JWT Configuration
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_THRESHOLD_MINUTES = 15
PENDING_TOKEN_EXPIRE_MINUTES = 10

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database

    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt

    Args:
        password: Plain text password

    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Data to encode in token (should include "sub" and "role")
        expires_delta: Optional expiration time delta

    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_access_token(
    token: str,
) -> Optional[dict]:  # CHANGED: Return dict instead of str
    """
    Decode JWT token and return payload

    Args:
        token: JWT token string

    Returns:
        Optional[dict]: Payload with username and role if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload  # CHANGED: Return full payload
    except JWTError:
        return None


def refresh_token_if_needed(token: str) -> Optional[str]:
    """
    Returns a new token if it's close to expiring, otherwise None
    """
    payload = decode_access_token(token)
    if not payload:
        return None

    exp = payload.get("exp")
    if not exp:
        return None

    time_remaining = datetime.utcfromtimestamp(exp) - datetime.utcnow()

    if time_remaining < timedelta(minutes=REFRESH_THRESHOLD_MINUTES):
        # Alisin ang exp para ma-regenerate
        new_data = {k: v for k, v in payload.items() if k != "exp"}
        return create_access_token(new_data)

    return None


# --- Google sign-in OTP challenge tokens ---


def generate_otp() -> str:
    """6-digit numeric OTP."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return pwd_context.hash(otp)


def verify_otp_hash(otp: str, otp_hash: str) -> bool:
    return pwd_context.verify(otp, otp_hash)


def create_pending_token(user_id: int, otp_id: int) -> str:
    """
    Short-lived token issued after a Google credential is verified but
    before the OTP step is completed. Not a login token — carries no role.
    """
    expire = datetime.utcnow() + timedelta(minutes=PENDING_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "otp_id": otp_id,
        "purpose": "google_otp",
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_pending_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise ValueError("Invalid or expired token")
    if payload.get("purpose") != "google_otp":
        raise ValueError("Invalid token purpose")
    return payload
