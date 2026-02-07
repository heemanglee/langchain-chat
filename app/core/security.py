"""Password hashing utilities using bcrypt."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

import bcrypt

_executor = ThreadPoolExecutor(max_workers=4)

DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt(rounds=12)).decode()


async def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode(),
    )


async def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: bcrypt.checkpw(plain.encode(), hashed.encode()),
    )
