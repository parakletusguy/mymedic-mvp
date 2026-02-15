"""
Identity Domain — Reusable FastAPI Dependencies.

These are the SHARED CONTRACTS that every other agent imports
to protect their own endpoints.

Usage in any domain router:
    from api.identity.dependencies import get_current_active_user, require_role

    @router.get("/protected")
    async def protected(user = Depends(get_current_active_user)):
        ...

    @router.get("/professionals-only")
    async def professionals_only(user = Depends(require_role("professional"))):
        ...
"""

from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.security import decode_token
from api.identity.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the access JWT and return the corresponding User row.

    Raises 401 if token is invalid, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Ensure the authenticated user's account is active.

    This is the primary dependency that other agents should use.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )
    return user


def require_role(*allowed_roles: str) -> Callable:
    """
    Factory that returns a dependency enforcing role-based access.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_only(): ...

        # Or inject the user:
        async def handler(user = Depends(require_role("professional"))):
            ...
    """

    async def _role_guard(
        user: User = Depends(get_current_active_user),
    ) -> User:
        if user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}.",
            )
        return user

    return _role_guard
