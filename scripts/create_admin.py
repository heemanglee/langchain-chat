"""Create an admin user in the database.

Usage:
    python -m scripts.create_admin --email admin@test.com --password Admin1234!
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, async_session_factory, engine
from app.core.security import hash_password
from app.models.user import User


async def create_admin(email: str, password: str, username: str) -> None:
    """Create an admin user if one does not already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as session:
        session: AsyncSession
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User with email '{email}' already exists (id={existing.id}).")
            return

        hashed = await hash_password(password)
        user = User(
            email=email,
            hashed_password=hashed,
            username=username,
            role="admin",
        )
        session.add(user)
        await session.commit()
        print(f"Admin user created: {email} (id={user.id})")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--username", default="admin", help="Admin username")
    args = parser.parse_args()

    asyncio.run(create_admin(args.email, args.password, args.username))


if __name__ == "__main__":
    main()
