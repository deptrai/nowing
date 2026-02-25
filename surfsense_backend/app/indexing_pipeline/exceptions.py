from litellm.exceptions import (
    APIConnectionError,
    APIResponseValidationError,
    AuthenticationError,
    BadGatewayError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
    UnprocessableEntityError,
)
from sqlalchemy.exc import IntegrityError, InvalidRequestError, OperationalError, SQLAlchemyError
from sqlalchemy.orm.exc import DetachedInstanceError

# Tuples for use directly in except clauses.
RETRYABLE_LLM_ERRORS = (
    RateLimitError,
    Timeout,
    ServiceUnavailableError,
    BadGatewayError,
    InternalServerError,
    APIConnectionError,
)

PERMANENT_LLM_ERRORS = (
    AuthenticationError,
    PermissionDeniedError,
    NotFoundError,
    BadRequestError,
    UnprocessableEntityError,
    APIResponseValidationError,
)

TRANSIENT_DB_ERRORS = (
    OperationalError,
    IntegrityError,
)

# Session is broken after these — re-raise instead of attempting further DB calls.
FATAL_DB_ERRORS = (
    InvalidRequestError,
    DetachedInstanceError,
)


# (LiteLLMEmbeddings, CohereEmbeddings, GeminiEmbeddings all normalize to RuntimeError).
EMBEDDING_ERRORS = (
    RuntimeError,  
    OSError,       
    MemoryError,   
    ValueError,    
)


class PipelineMessages:
    RATE_LIMIT        = "LLM rate limit exceeded. Will retry on next sync."
    LLM_TIMEOUT       = "LLM request timed out. Will retry on next sync."
    LLM_UNAVAILABLE   = "LLM service temporarily unavailable. Will retry on next sync."
    LLM_BAD_GATEWAY   = "LLM gateway error. Will retry on next sync."
    LLM_SERVER_ERROR  = "LLM internal server error. Will retry on next sync."
    LLM_CONNECTION    = "Could not reach the LLM service. Check network connectivity."

    LLM_AUTH          = "LLM authentication failed. Check your API key."
    LLM_PERMISSION    = "LLM request denied. Check your account permissions."
    LLM_NOT_FOUND     = "LLM model not found. Check your model configuration."
    LLM_BAD_REQUEST   = "LLM rejected the request. Document content may be invalid."
    LLM_UNPROCESSABLE = "Document exceeds the LLM context window even after optimization."
    LLM_RESPONSE      = "LLM returned an invalid response."

    DB_TRANSIENT      = "Database error during indexing. Will retry on next sync."
    DB_SESSION_DEAD   = "Database session is in an unrecoverable state."

    EMBEDDING_FAILED  = "Embedding failed. Check your embedding model configuration or service."
    EMBEDDING_MODEL   = "Embedding model files are missing or corrupted."
    EMBEDDING_MEMORY  = "Not enough memory to embed this document."
    EMBEDDING_INPUT   = "Document content is invalid for the embedding model."

    CHUNKING_OVERFLOW = "Document structure is too deeply nested to chunk."


def llm_retryable_message(exc: Exception) -> str:
    if isinstance(exc, RateLimitError):
        return PipelineMessages.RATE_LIMIT
    if isinstance(exc, Timeout):
        return PipelineMessages.LLM_TIMEOUT
    if isinstance(exc, ServiceUnavailableError):
        return PipelineMessages.LLM_UNAVAILABLE
    if isinstance(exc, BadGatewayError):
        return PipelineMessages.LLM_BAD_GATEWAY
    if isinstance(exc, InternalServerError):
        return PipelineMessages.LLM_SERVER_ERROR
    if isinstance(exc, APIConnectionError):
        return PipelineMessages.LLM_CONNECTION
    return str(exc)


def llm_permanent_message(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return PipelineMessages.LLM_AUTH
    if isinstance(exc, PermissionDeniedError):
        return PipelineMessages.LLM_PERMISSION
    if isinstance(exc, NotFoundError):
        return PipelineMessages.LLM_NOT_FOUND
    if isinstance(exc, BadRequestError):
        return PipelineMessages.LLM_BAD_REQUEST
    if isinstance(exc, UnprocessableEntityError):
        return PipelineMessages.LLM_UNPROCESSABLE
    if isinstance(exc, APIResponseValidationError):
        return PipelineMessages.LLM_RESPONSE
    return str(exc)


def embedding_message(exc: Exception) -> str:
    if isinstance(exc, RuntimeError):
        return PipelineMessages.EMBEDDING_FAILED
    if isinstance(exc, OSError):
        return PipelineMessages.EMBEDDING_MODEL
    if isinstance(exc, MemoryError):
        return PipelineMessages.EMBEDDING_MEMORY
    if isinstance(exc, ValueError):
        return PipelineMessages.EMBEDDING_INPUT
    return str(exc)
