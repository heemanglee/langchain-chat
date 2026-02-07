"""Tests for UserRepository."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repo import UserRepository


@pytest.fixture
def repo(db_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session)


class TestUserRepository:
    """Tests for user CRUD operations."""

    async def test_create_user(
        self, repo: UserRepository, db_session: AsyncSession
    ) -> None:
        user = await repo.create(
            email="new@test.com",
            hashed_password="hashed",
            username="newuser",
        )
        assert user.id is not None
        assert user.email == "new@test.com"
        assert user.role == "user"

    async def test_find_by_email(
        self, repo: UserRepository, db_session: AsyncSession
    ) -> None:
        await repo.create(email="find@test.com", hashed_password="h", username="u")
        await db_session.commit()
        found = await repo.find_by_email("find@test.com")
        assert found is not None
        assert found.email == "find@test.com"

    async def test_find_by_email_not_found(self, repo: UserRepository) -> None:
        found = await repo.find_by_email("nonexistent@test.com")
        assert found is None

    async def test_find_by_id(
        self, repo: UserRepository, db_session: AsyncSession
    ) -> None:
        user = await repo.create(
            email="byid@test.com", hashed_password="h", username="u"
        )
        await db_session.commit()
        found = await repo.find_by_id(user.id)
        assert found is not None
        assert found.email == "byid@test.com"

    async def test_exists_by_email_true(
        self, repo: UserRepository, db_session: AsyncSession
    ) -> None:
        await repo.create(email="exists@test.com", hashed_password="h", username="u")
        await db_session.commit()
        assert await repo.exists_by_email("exists@test.com") is True

    async def test_exists_by_email_false(self, repo: UserRepository) -> None:
        assert await repo.exists_by_email("nope@test.com") is False
