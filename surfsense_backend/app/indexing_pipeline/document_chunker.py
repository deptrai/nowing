from app.config import config


def chunk_text(text: str) -> list[str]:
    """Chunk a text string using the configured chunker and return the chunk texts."""
    return [c.text for c in config.chunker_instance.chunk(text)]
