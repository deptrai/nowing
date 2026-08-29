"""Config domain: llm."""

from __future__ import annotations

import os

from chonkie import AutoEmbeddings, CodeChunker, RecursiveChunker
from rerankers import Reranker

from app.config._helpers import (
    BASE_DIR,
    _env_float,
    _env_int,
    load_global_image_gen_configs,
    load_global_llm_configs,
    load_image_gen_router_settings,
    load_openrouter_integration_settings,
    load_router_settings,
)
from app.config.embedding_settings import (
    build_embedding_kwargs,
    resolve_embedding_base_url,
)
from app.services.global_model_catalog import (
    materialize_global_model_catalog as _materialize_global_model_catalog,
)

# Hybrid LLM Router (Story 26.3)
HYBRID_ENABLE_LOCAL_VLLM = (
    os.getenv("HYBRID_ENABLE_LOCAL_VLLM", "TRUE").upper() == "TRUE"
)
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
HYBRID_GEMINI_RPM_LIMIT = _env_int("HYBRID_GEMINI_RPM_LIMIT", 15)
HYBRID_GEMINI_TPM_LIMIT = _env_int("HYBRID_GEMINI_TPM_LIMIT", 1_000_000)
HYBRID_GEMINI_RPD_LIMIT = _env_int("HYBRID_GEMINI_RPD_LIMIT", 1500)
HYBRID_OFF_PEAK_HOURS = os.getenv("HYBRID_OFF_PEAK_HOURS", "22-06")
HYBRID_PEAK_PRICE_MULTIPLIER = _env_float("HYBRID_PEAK_PRICE_MULTIPLIER", 2.0)
HYBRID_FORCE_DEEP_REASONING = (
    os.getenv("HYBRID_FORCE_DEEP_REASONING", "FALSE").upper() == "TRUE"
)
HYBRID_VLLM_QUEUE_TIMEOUT_SECONDS = _env_float(
    "HYBRID_VLLM_QUEUE_TIMEOUT_SECONDS", 8.0
)

# LLM instances are now managed per-user through the LLMConfig system
# Legacy environment variables removed in favor of user-specific configurations

# True when an operator-provided global_llm_config.yaml is present.
# Used to gate the per-workspace LLM onboarding flow: when a global
# config file exists, workspaces inherit it and onboarding is skipped.
GLOBAL_LLM_CONFIG_FILE_EXISTS = (
    BASE_DIR / "app" / "config" / "global_llm_config.yaml"
).exists() or bool(os.environ.get("GLOBAL_LLM_CONFIG_B64"))

# Global LLM Configurations (optional)
# Load from global_llm_config.yaml if available
# These can be used as default options for users
GLOBAL_LLM_CONFIGS = load_global_llm_configs()

# Router settings for Auto mode (LiteLLM Router load balancing)
ROUTER_SETTINGS = load_router_settings()

# Global Image Generation Configurations (optional)
GLOBAL_IMAGE_GEN_CONFIGS = load_global_image_gen_configs()

# Router settings for Image Generation Auto mode
IMAGE_GEN_ROUTER_SETTINGS = load_image_gen_router_settings()

# Virtual GLOBAL connection/model catalog. This is server-only metadata
# derived from global_llm_config.yaml; GLOBAL keys are not stored in DB.
GLOBAL_CONNECTIONS, GLOBAL_MODELS = _materialize_global_model_catalog(
    chat_configs=GLOBAL_LLM_CONFIGS,
    image_configs=GLOBAL_IMAGE_GEN_CONFIGS,
)
del _materialize_global_model_catalog

# OpenRouter Integration settings (optional)
OPENROUTER_INTEGRATION_SETTINGS = load_openrouter_integration_settings()

# Chonkie Configuration | Edit this to your needs
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_BASE_URL = resolve_embedding_base_url()
# Azure OpenAI credentials from environment variables
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

# Pass provider-specific settings to embeddings when supported.
embedding_kwargs = build_embedding_kwargs(embedding_model=EMBEDDING_MODEL)

embedding_model_instance = AutoEmbeddings.get_embeddings(
    EMBEDDING_MODEL,
    **embedding_kwargs,
)
is_local_embedding_model = "://" not in (EMBEDDING_MODEL or "")
chunker_instance = RecursiveChunker(
    chunk_size=getattr(embedding_model_instance, "max_seq_length", 512)
)
code_chunker_instance = CodeChunker(
    chunk_size=getattr(embedding_model_instance, "max_seq_length", 512)
)

# Reranker's Configuration | Pinecone, Cohere etc. Read more at https://github.com/AnswerDotAI/rerankers?tab=readme-ov-file#usage
RERANKERS_ENABLED = os.getenv("RERANKERS_ENABLED", "FALSE").upper() == "TRUE"
if RERANKERS_ENABLED:
    RERANKERS_MODEL_NAME = os.getenv("RERANKERS_MODEL_NAME")
    RERANKERS_MODEL_TYPE = os.getenv("RERANKERS_MODEL_TYPE")
    reranker_instance = Reranker(
        model_name=RERANKERS_MODEL_NAME,
        model_type=RERANKERS_MODEL_TYPE,
    )
else:
    reranker_instance = None

# Validation Checks
# Check embedding dimension
if (
    hasattr(embedding_model_instance, "dimension")
    and embedding_model_instance.dimension > 2000
):
    raise ValueError(
        f"Embedding dimension for Model: {EMBEDDING_MODEL} "
        f"has {embedding_model_instance.dimension} dimensions, which "
        f"exceeds the maximum of 2000 allowed by PGVector."
    )



__all__ = ['AZURE_OPENAI_API_KEY', 'AZURE_OPENAI_ENDPOINT', 'EMBEDDING_BASE_URL', 'EMBEDDING_MODEL', 'GLOBAL_CONNECTIONS', 'GLOBAL_IMAGE_GEN_CONFIGS', 'GLOBAL_LLM_CONFIGS', 'GLOBAL_LLM_CONFIG_FILE_EXISTS', 'GLOBAL_MODELS', 'HYBRID_ENABLE_LOCAL_VLLM', 'HYBRID_FORCE_DEEP_REASONING', 'HYBRID_GEMINI_RPD_LIMIT', 'HYBRID_GEMINI_RPM_LIMIT', 'HYBRID_GEMINI_TPM_LIMIT', 'HYBRID_OFF_PEAK_HOURS', 'HYBRID_PEAK_PRICE_MULTIPLIER', 'HYBRID_VLLM_QUEUE_TIMEOUT_SECONDS', 'IMAGE_GEN_ROUTER_SETTINGS', 'OPENROUTER_INTEGRATION_SETTINGS', 'RERANKERS_ENABLED', 'ROUTER_SETTINGS', 'VLLM_BASE_URL', 'chunker_instance', 'code_chunker_instance', 'embedding_kwargs', 'embedding_model_instance', 'is_local_embedding_model', 'reranker_instance']
