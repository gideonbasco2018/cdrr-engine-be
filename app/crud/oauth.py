# app/crud/oauth.py
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.oauth_otp import OAuthOTP
from app.core.security import (
    generate_otp,
    hash_otp,
    verify_otp_hash,
    create_pending_token,
)


def get_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_by_oauth_sub(db: Session, oauth_sub: str):
    return db.query(User).filter(User.oauth_sub == oauth_sub).first()


def _username_taken(db: Session, username: str) -> bool:
    return db.query(User).filter(User.username == username).first() is not None


def create_oauth_user(
    db: Session,
    *,
    email: str,
    first_name: str,
    surname: str,
    oauth_provider: str,
    oauth_sub: str,
):
    base_username = email.split("@")[0]
    username = base_username
    suffix = 1
    while _username_taken(db, username):
        suffix += 1
        username = f"{base_username}{suffix}"

    user = User(
        email=email,
        username=username,
        hashed_password=None,
        first_name=first_name or "",
        surname=surname or "",
        role=UserRole.USER,
        oauth_provider=oauth_provider,
        oauth_sub=oauth_sub,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def link_oauth_to_existing_user(
    db: Session, user: User, oauth_provider: str, oauth_sub: str
):
    user.oauth_provider = oauth_provider
    user.oauth_sub = oauth_sub
    db.commit()
    db.refresh(user)
    return user


def create_otp_challenge(db: Session, user: User) -> tuple[str, str]:
    """
    Creates a new OTP row for the user, returns (plaintext_otp, pending_token).
    Invalidate any previous unconsumed OTPs for this user first.
    """
    db.query(OAuthOTP).filter(
        OAuthOTP.user_uuid == user.user_uuid, OAuthOTP.consumed == False  # noqa: E712
    ).update({"consumed": True})

    plaintext_otp = generate_otp()
    otp_row = OAuthOTP(user_uuid=user.user_uuid, otp_hash=hash_otp(plaintext_otp))
    db.add(otp_row)
    db.commit()
    db.refresh(otp_row)

    # pending_token still keyed on the integer user.id — that identifier is
    # unrelated to the OAuthOTP FK change and doesn't need to move to uuid.
    pending_token = create_pending_token(user_id=user.id, otp_id=otp_row.id)
    return plaintext_otp, pending_token


def verify_otp_challenge(db: Session, otp_id: int, user_id: int, otp: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    otp_row = (
        db.query(OAuthOTP)
        .filter(OAuthOTP.id == otp_id, OAuthOTP.user_uuid == user.user_uuid)
        .first()
    )
    if not otp_row:
        raise ValueError("OTP challenge not found")
    if otp_row.consumed:
        raise ValueError("OTP already used")

    # MySQL returns naive datetimes even for DateTime(timezone=True) columns.
    # Values are always written as UTC, so treat naive datetimes as UTC.
    expires_at = otp_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise ValueError("OTP expired")

    if otp_row.attempts >= otp_row.max_attempts:
        raise ValueError("Too many attempts")

    otp_row.attempts += 1

    if not verify_otp_hash(otp, otp_row.otp_hash):
        db.commit()
        raise ValueError("Incorrect OTP")

    otp_row.consumed = True
    db.commit()

    return user
