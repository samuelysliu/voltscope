from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_session
from app.models import User
from app.security.jwt import decode_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def current_user_id(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("UNAUTHORIZED", "Authentication required", 401)
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise AppError("UNAUTHORIZED", "Invalid token", 401) from exc
    return str(payload["sub"])


async def current_user(session: SessionDep, user_id: str = Depends(current_user_id)) -> User:
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError("UNAUTHORIZED", "Authentication required", 401)
    return user


async def current_admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise AppError("FORBIDDEN", "Admin role required", 403)
    return user


async def current_verified_member(user: User = Depends(current_user)) -> User:
    if not user.email_verified:
        raise AppError("EMAIL_NOT_VERIFIED", "Email verification required", 403)
    return user
