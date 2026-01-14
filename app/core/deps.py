"""
FastAPI Dependencies
Database session and authentication dependencies
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List  # ADD THIS

from app.db.session import get_db
from app.core.security import decode_access_token
from app.crud import user as crud_user
from app.models.user import User, UserRole  # ADD UserRole import

# OAuth2 scheme for token authentication

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/routes/auth/login")

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        db: Database session
        token: JWT token from Authorization header
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode token - CHANGED: now returns dict instead of string
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    # Get username from payload
    username = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    # Get user from database
    user = crud_user.get_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user (must be active)
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User: Current active user
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


# ADD THIS NEW FUNCTION: Role-based access control
def require_role(allowed_roles: List[UserRole]):
    """
    Dependency factory to check if user has required role
    
    Args:
        allowed_roles: List of UserRole enums that are allowed to access the endpoint
        
    Returns:
        Dependency function that checks user role
        
    Usage:
        @router.get("/admin/dashboard")
        def admin_dashboard(
            current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.SUPERADMIN]))
        ):
            return {"message": "Admin dashboard"}
            
        @router.delete("/superadmin/delete-user/{user_id}")
        def delete_user(
            user_id: int,
            current_user: User = Depends(require_role([UserRole.SUPERADMIN]))
        ):
            return {"message": "User deleted"}
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        """
        Check if current user has one of the required roles
        
        Args:
            current_user: Current authenticated and active user
            
        Returns:
            User: Current user if they have required role
            
        Raises:
            HTTPException: If user doesn't have required role
        """
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join([role.value for role in allowed_roles])}"
            )
        return current_user
    
    return role_checker


# ADD THESE HELPER FUNCTIONS: Shorthand for common role checks
def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Shorthand dependency: Require Admin or SuperAdmin role
    
    Usage:
        @router.get("/admin/users")
        def get_users(current_user: User = Depends(require_admin)):
            return users
    """
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPERADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def require_superadmin(current_user: User = Depends(get_current_active_user)) -> User:
    """
    Shorthand dependency: Require SuperAdmin role only
    
    Usage:
        @router.delete("/superadmin/users/{user_id}")
        def delete_user(
            user_id: int,
            current_user: User = Depends(require_superadmin)
        ):
            return {"deleted": True}
    """
    if current_user.role != UserRole.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SuperAdmin access required"
        )
    return current_user