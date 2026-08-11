"""Canonical scraper -> chainlens-research chunk normalization."""

from .schemas import Chunk, ChunkMetadata, ChunkValidationError
from .serializer import to_chunks

__all__ = ["Chunk", "ChunkMetadata", "ChunkValidationError", "to_chunks"]
