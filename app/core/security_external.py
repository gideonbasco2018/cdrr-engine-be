# app/core/security_external.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

bearer_scheme = HTTPBearer()


async def verify_bearer_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if credentials.credentials != settings.EXTERNAL_SYSTEM_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
