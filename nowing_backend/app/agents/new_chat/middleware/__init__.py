"""Middleware components for the Nowing new chat agent."""

from app.agents.new_chat.middleware.crypto_data_cache import (
    CryptoDataCacheMiddleware,
)
from app.agents.new_chat.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
)
from app.agents.new_chat.middleware.filesystem import (
    NowingFilesystemMiddleware,
)
from app.agents.new_chat.middleware.knowledge_search import (
    KnowledgeBaseSearchMiddleware,
)
from app.agents.new_chat.middleware.memory_injection import (
    MemoryInjectionMiddleware,
)

__all__ = [
    "CryptoDataCacheMiddleware",
    "DedupHITLToolCallsMiddleware",
    "KnowledgeBaseSearchMiddleware",
    "MemoryInjectionMiddleware",
    "NowingFilesystemMiddleware",
]
