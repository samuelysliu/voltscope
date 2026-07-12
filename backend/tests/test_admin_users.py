from datetime import datetime

import pytest

from app.api.v1.admin import delete_admin_user
from app.models import User


class FakeSession:
    def __init__(self, user: User) -> None:
        self.user = user
        self.committed = False
        self.executed = False

    async def get(self, model: type[User], user_id: str) -> User | None:
        assert model is User
        return self.user if self.user.id == user_id else None

    async def commit(self) -> None:
        self.committed = True

    async def execute(self, statement: object) -> None:
        self.executed = True


@pytest.mark.asyncio
async def test_delete_user_releases_original_email() -> None:
    user = User(
        id="11111111-1111-1111-1111-111111111111",
        email="member@example.com",
        password_hash="unused",
        display_name="Member",
        role="member",
        email_verified=True,
        is_active=True,
    )
    admin = User(
        id="22222222-2222-2222-2222-222222222222",
        email="admin@example.com",
        password_hash="unused",
        display_name="Admin",
        role="admin",
        email_verified=True,
        is_active=True,
    )
    session = FakeSession(user)

    result = await delete_admin_user(user.id, session, admin)

    assert result == {"ok": True}
    assert user.email == "deleted-11111111-1111-1111-1111-111111111111@users.invalid"
    assert user.email != "member@example.com"
    assert user.is_active is False
    assert isinstance(user.deleted_at, datetime)
    assert session.executed is True
    assert session.committed is True
