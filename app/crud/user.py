from app.models.user import User
from app.schemas.user import UserCreate
from sqlalchemy.ext.asyncio import AsyncSession

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    # Example logic
    user = await db.get(User, email)
    if user and user.password == password:  # replace with proper hash check
        return user
    return None
