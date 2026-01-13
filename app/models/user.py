from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from app.db.base_class import Base
import enum

# Define Role Enum
class UserRole(str, enum.Enum):
    USER = "User"
    ADMIN = "Admin"
    SUPERADMIN = "SuperAdmin"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # login identifiers
    email = Column(String(255), nullable=False, unique=True, index=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # personal info
    first_name = Column(String(100), nullable=False)
    surname = Column(String(100), nullable=False)
    position = Column(String(100), nullable=True)
    
    # role
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    
    # status
    is_active = Column(Boolean, default=True)
    
    # timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )