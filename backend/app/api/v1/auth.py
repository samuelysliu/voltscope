import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select

from app.api.v1.deps import SessionDep, current_user, current_user_id
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import EmailVerificationToken, User
from app.schemas.auth import LoginRequest, LogoutResponse, RegisterRequest, RegisterResponse, TokenResponse, UserOut, VerifyEmailResponse
from app.security.jwt import create_access_token
from app.security.passwords import hash_password, verify_password
from app.services.email import send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def serialize_user(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        email_verified=user.email_verified,
    )


async def create_email_verification(session: SessionDep, user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=token_hash(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )
    return raw_token


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(payload: RegisterRequest, session: SessionDep) -> RegisterResponse:
    email = payload.email.lower()
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise AppError("EMAIL_ALREADY_REGISTERED", "Email already registered", 409)
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role="member",
        email_verified=False,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    raw_token = await create_email_verification(session, user)
    settings = get_settings()
    verification_url = f"{str(settings.frontend_url).rstrip('/')}/verify-email?token={raw_token}"
    await send_verification_email(user.email, verification_url)
    await session.commit()
    await session.refresh(user)
    return RegisterResponse(
        user=serialize_user(user),
        verification_url=verification_url if settings.app_env == "local" else None,
    )


@router.get("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(token: str, session: SessionDep) -> VerifyEmailResponse:
    verification = await session.scalar(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_hash(token),
            EmailVerificationToken.used_at.is_(None),
        )
    )
    if verification is None or verification.expires_at < datetime.now(UTC):
        raise AppError("INVALID_VERIFICATION_TOKEN", "Invalid or expired verification token", 400)
    user = await session.get(User, verification.user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "User not found", 404)
    user.email_verified = True
    verification.used_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return VerifyEmailResponse(ok=True, user=serialize_user(user))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    user = await session.scalar(
        select(User).where(
            or_(User.email == payload.account, User.display_name == payload.account),
            User.is_active.is_(True),
        )
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Invalid account or password", 401)
    user.last_login_at = datetime.now(UTC)
    await session.commit()
    return TokenResponse(access_token=create_access_token(user.id, {"role": user.role}))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return serialize_user(user)


@router.post("/logout", response_model=LogoutResponse)
async def logout() -> LogoutResponse:
    return LogoutResponse(ok=True)
