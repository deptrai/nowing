"""Parser from legacy markdown memory into structured memory facts."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.db import MemorySourceType, MemoryType
from app.services.memory.document import MemoryBullet, parse_memory_document


@dataclass
class MemoryFact:
    content: str
    type: str = MemoryType.SEMANTIC.value
    source_type: str = MemorySourceType.MANUAL.value
    tags: list[str] = field(default_factory=list)


def parse_memory_markdown_to_facts(markdown: str) -> list[MemoryFact]:
    """Turn a markdown memory document into structured facts.

    Each dated bullet under an explicit ``##`` section becomes one fact.
    """
    facts: list[MemoryFact] = []
    document = parse_memory_document(markdown)
    for section in document.sections:
        for line in section.lines:
            if isinstance(line, MemoryBullet):
                facts.append(
                    MemoryFact(
                        content=line.text,
                        type=MemoryType.SEMANTIC.value,
                        source_type=MemorySourceType.MANUAL.value,
                    )
                )
    return facts
