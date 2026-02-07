"""Vector store configuration."""

from pathlib import Path

from pydantic import BaseModel


class VectorStoreConfig(BaseModel, frozen=True):
    """Vector store settings."""

    path: Path
    chunk_size: int
    chunk_overlap: int
