from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UsageBreakdownItem(BaseModel):
    """A single bucket of usage aggregated by a dimension key."""

    key: str
    total_tokens: int
    cost_micros: int

    model_config = ConfigDict(from_attributes=True)


class UsageSummaryResponse(BaseModel):
    """Full usage/credit summary for a workspace over a date range."""

    current_balance_micros: int
    reserved_micros: int
    total_tokens: int
    total_cost_micros: int
    start_date: datetime
    end_date: datetime
    by_usage_type: list[UsageBreakdownItem]
    by_model: list[UsageBreakdownItem]
    by_provider: list[UsageBreakdownItem]

    model_config = ConfigDict(from_attributes=True)


class UsageTimeSeriesPoint(BaseModel):
    """One bucket of a usage/cost time series."""

    period: str
    total_tokens: int
    cost_micros: int

    model_config = ConfigDict(from_attributes=True)


class UsageTimeSeriesResponse(BaseModel):
    """Time-series response for cost and tokens over time."""

    granularity: str
    points: list[UsageTimeSeriesPoint]

    model_config = ConfigDict(from_attributes=True)


class UsageTransactionItem(BaseModel):
    """A unified credit-related transaction for the transaction history list."""

    type: str
    amount_micros: int
    description: str | None
    status: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsageTransactionsResponse(BaseModel):
    """Paginated list of credit transactions."""

    transactions: list[UsageTransactionItem]
    total: int

    model_config = ConfigDict(from_attributes=True)


class ServiceCategory(str):
    AI_GENERATION = "AI Generation"
    WEB_SEARCH = "Web Search"
    SOCIAL_MEDIA = "Social Media"
    PHONE_WATERFALL = "Phone Waterfall"
    OUTCOME_MEETINGS = "Outcome Meetings"


class ServiceBreakdownItem(BaseModel):
    category: str
    total_tokens: int = 0
    cost_micros: int = 0
    event_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ServiceBreakdownResponse(BaseModel):
    workspace_id: int
    start_date: datetime
    end_date: datetime
    items: list[ServiceBreakdownItem]

    model_config = ConfigDict(from_attributes=True)


class PerTurnUsageItem(BaseModel):
    """One turn/event of token usage with cost and capability attribution."""

    turn_key: str
    turn_type: str
    created_at: datetime
    capability: str
    resolved_model: str
    llm_tokens: int
    embedding_tokens: int
    recall_tokens: int
    cost_micros: int
    memories_created: int
    citations_generated: int

    model_config = ConfigDict(from_attributes=True)


class PerTurnUsageResponse(BaseModel):
    """Per-turn usage breakdown for a workspace over a date range."""

    workspace_id: int
    start_date: datetime
    end_date: datetime
    items: list[PerTurnUsageItem]
    reconcile_warning: bool

    model_config = ConfigDict(from_attributes=True)
