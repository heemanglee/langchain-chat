"""Tests for password hashing utilities."""

from app.core.security import DUMMY_HASH, hash_password, verify_password


class TestPasswordHashing:
    """Tests for bcrypt password operations."""

    async def test_hash_and_verify(self) -> None:
        hashed = await hash_password("MyPassword123!")
        assert await verify_password("MyPassword123!", hashed) is True

    async def test_wrong_password_fails(self) -> None:
        hashed = await hash_password("Correct1!")
        assert await verify_password("Wrong1!", hashed) is False

    async def test_dummy_hash_exists(self) -> None:
        assert DUMMY_HASH.startswith("$2")

    async def test_dummy_hash_does_not_match_real(self) -> None:
        assert await verify_password("realpassword", DUMMY_HASH) is False
