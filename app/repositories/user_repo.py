"""User repository for database operations."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Encapsulates user-related database queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_email(self, email: str) -> User | None:
        """Find a user by email address."""
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def find_by_id(self, user_id: int) -> User | None:
        """Find a user by primary key."""
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        hashed_password: str,
        username: str,
        role: str = "user",
    ) -> User:
        """Create a new user record."""
        user = User(
            email=email,
            hashed_password=hashed_password,
            username=username,
            role=role,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def exists_by_email(self, email: str) -> bool:
        """Check if a user with this email exists."""
        result = await self._session.execute(select(User.id).where(User.email == email))
        return result.scalar_one_or_none() is not None
