"""File upload configuration."""

from pydantic import BaseModel


class FileUploadConfig(BaseModel, frozen=True):
    """File upload settings."""

    max_file_size_mb: int
    allowed_extensions: str

    @property
    def allowed_extensions_list(self) -> list[str]:
        """Get allowed extensions as a list."""
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
