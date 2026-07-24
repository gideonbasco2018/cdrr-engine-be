# app/models/users.py
from sqlalchemy.sql import func
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum,
)
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum
from sqlalchemy.dialects.mysql import TINYINT


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
    alias = Column(String(100), nullable=True)

    # role
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)

    # access request
    access_request = Column(String(255), nullable=True)

    # 🔗 ASSOCIATION OBJECT RELATIONSHIP
    user_groups = relationship(
        "UserGroup", back_populates="user", cascade="all, delete-orphan"
    )

    # 🔁 CONVENIENCE MANY-TO-MANY (read-only)
    groups = relationship("Group", secondary="user_groups", viewonly=True)

    # status
    is_active = Column(Boolean, default=True)

    # timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    has_upload_history = Column(
        TINYINT(1),
        nullable=False,
        default=0,
        comment="Show upload history on dashboard",
    )

    profile_picture_url = Column(String(500), nullable=True)
    profile_picture_drive_id = Column(String(255), nullable=True)

    # 🔙 Backward compatibility (KEEP SAFE)
    @property
    def group_id(self):
        return self.groups[0].id if self.groups else None

    @property
    def group(self):
        return self.groups[0] if self.groups else None
