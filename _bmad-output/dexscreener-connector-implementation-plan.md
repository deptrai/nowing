# DexScreener Connector - Implementation Plan

## 📋 Tổng Quan

Sau khi research kỹ [DexScreener API Documentation](https://docs.dexscreener.com/api/reference) và phân tích source code Nowing, đây là phương án implementation chính xác nhất cho DexScreener Connector.

## 🔍 DexScreener API Research Findings

### Base Information
- **Base URL**: `https://api.dexscreener.com`
- **Authentication**: KHÔNG cần API key (public API)
- **Rate Limits**: 
  - Profile/Ads endpoints: 60 requests/minute
  - Pair/Token endpoints: **300 requests/minute**
- **Max Results**: Search endpoint trả về tối đa 30 pairs

### Core Endpoints

#### 1. Search Pairs
```
GET /latest/dex/search?q={query}
Rate Limit: 300 req/min
Max Results: 30 pairs
```

**Use Case**: Tìm kiếm trading pairs theo token name, symbol, hoặc address

**Response Structure**:
```json
{
  "schemaVersion": "1.0.0",
  "pairs": [
    {
      "chainId": "solana",
      "dexId": "raydium",
      "url": "https://dexscreener.com/solana/...",
      "pairAddress": "...",
      "baseToken": {
        "address": "...",
        "name": "Token Name",
        "symbol": "TKN"
      },
      "quoteToken": {
        "address": "...",
        "name": "USD Coin",
        "symbol": "USDC"
      },
      "priceNative": "0.00123",
      "priceUsd": "1.23",
      "txns": {
        "m5": { "buys": 10, "sells": 5 },
        "h1": { "buys": 100, "sells": 50 },
        "h6": { "buys": 500, "sells": 250 },
        "h24": { "buys": 2000, "sells": 1000 }
      },
      "volume": {
        "h24": 1000000,
        "h6": 250000,
        "h1": 50000,
        "m5": 5000
      },
      "priceChange": {
        "m5": 1.5,
        "h1": 5.2,
        "h6": 10.5,
        "h24": 25.3
      },
      "liquidity": {
        "usd": 500000,
        "base": 1000000,
        "quote": 500000
      },
      "fdv": 10000000,
      "marketCap": 5000000,
      "pairCreatedAt": 1640000000000
    }
  ]
}
```

#### 2. Get Token Pairs
```
GET /latest/dex/tokens/{chainId}/{tokenAddress}
Rate Limit: 300 req/min
```

**Use Case**: Lấy tất cả pools/pairs của một token cụ thể

#### 3. Get Specific Pair
```
GET /latest/dex/pairs/{chainId}/{pairAddress}
Rate Limit: 300 req/min
```

**Use Case**: Lấy thông tin chi tiết của một pair cụ thể

#### 4. Get Multiple Tokens
```
GET /tokens/v1/{chainId}/{tokenAddresses}
Rate Limit: 300 req/min
Max: 30 addresses (comma-separated)
```

**Use Case**: Batch query nhiều tokens cùng lúc

## 🏗️ Nowing Architecture Analysis

### Pattern Đã Xác Định

#### 1. Connector Class Pattern
**File**: `app/connectors/{name}_connector.py`

**Responsibilities**:
- Initialize với API credentials (nếu cần)
- Methods để fetch data từ external API
- Methods để format data sang markdown
- Error handling cho API calls

**Example từ LumaConnector**:
```python
class LumaConnector:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self.base_url = "https://api.lu.ma"
    
    def make_request(self, endpoint: str, params: dict | None = None):
        # Handle API calls with error handling
        
    def get_events_by_date_range(self, start_date: str, end_date: str):
        # Fetch data from API
        
    def format_event_to_markdown(self, event: dict) -> str:
        # Convert to markdown for indexing
```

#### 2. Indexer Pattern
**File**: `app/tasks/connector_indexers/{name}_indexer.py`

**Responsibilities**:
- Async function `index_{name}()` 
- Get connector từ database
- Extract config (API keys, etc.)
- Initialize connector class
- Fetch data từ API
- Loop qua items:
  - Generate `unique_identifier_hash` (để track duplicates)
  - Generate `content_hash` (để detect content changes)
  - Check existing documents
  - Create/Update `Document` objects với:
    - `chunks` (text chunks cho vector search)
    - `embedding` (vector embedding)
    - `metadata` (structured data)
- Batch commit to database
- Update `last_indexed_at` timestamp

**Key Functions Used**:
```python
from app.utils.document_converters import (
    create_document_chunks,
    generate_content_hash,
    generate_document_summary,
    generate_unique_identifier_hash,
)
```

#### 3. Routes Pattern
**File**: `app/routes/{name}_add_connector_route.py`

**Endpoints**:
- `POST /connectors/{name}/add` - Add/Update connector
- `DELETE /connectors/{name}` - Delete connector
- `GET /connectors/{name}/test` - Test connection

**Example từ luma_add_connector_route.py**:
```python
@router.post("/connectors/luma/add")
async def add_luma_connector(
    request: AddLumaConnectorRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    # Check existing connector
    # Create or update SearchSourceConnector
    # Store config in connector.config JSON field
```

#### 4. Database Schema
**File**: `app/db.py`

**SearchSourceConnectorType Enum**:
```python
class SearchSourceConnectorType(str, Enum):
    LUMA_CONNECTOR = "LUMA_CONNECTOR"
    SLACK_CONNECTOR = "SLACK_CONNECTOR"
    # ... thêm DEXSCREENER_CONNECTOR
```

**SearchSourceConnector Model**:
```python
class SearchSourceConnector(Base):
    id: int
    name: str
    connector_type: SearchSourceConnectorType
    config: dict  # JSON field để store API keys, settings
    search_space_id: int
    user_id: UUID
    is_indexable: bool
    last_indexed_at: datetime
```

#### 5. Celery Tasks
**File**: `app/tasks/celery_tasks/connector_tasks.py`

**Pattern**:
```python
@celery_app.task(name="index_luma_events", bind=True)
def index_luma_events_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    # Wrapper cho async indexer function
    return asyncio.run(_index_luma_events(...))
```

#### 6. Periodic Scheduler
**File**: `app/utils/periodic_scheduler.py`

**Mapping**:
```python
CONNECTOR_TYPE_TO_TASK_NAME = {
    SearchSourceConnectorType.LUMA_CONNECTOR: "index_luma_events",
    # ... thêm mapping cho DexScreener
}

CONNECTOR_TYPE_TO_TASK = {
    SearchSourceConnectorType.LUMA_CONNECTOR: index_luma_events_task,
    # ... thêm task cho DexScreener
}
```

## 📝 Implementation Plan

### Phase 1: Core Components

#### 1.1. Database Schema Update

**File**: `app/db.py`

**Changes**:
```python
class SearchSourceConnectorType(str, Enum):
    # ... existing types
    DEXSCREENER_CONNECTOR = "DEXSCREENER_CONNECTOR"

class DocumentType(str, Enum):
    # ... existing types
    DEXSCREENER_CONNECTOR = "DEXSCREENER_CONNECTOR"
```

#### 1.2. Connector Class

**File**: `app/connectors/dexscreener_connector.py`

Xem full implementation trong artifacts.

#### 1.3. Indexer

**File**: `app/tasks/connector_indexers/dexscreener_indexer.py`

Xem full implementation trong artifacts.

### Phase 2: API Routes & Integration

#### 2.1. Routes

**File**: `app/routes/dexscreener_add_connector_route.py`

Xem full implementation trong artifacts.

#### 2.2. Celery Task

**File**: `app/tasks/celery_tasks/connector_tasks.py`

**Add to existing file**:
```python
# Add import
from app.tasks.connector_indexers import index_dexscreener_pairs

# Add task
@celery_app.task(name="index_dexscreener_pairs", bind=True)
def index_dexscreener_pairs_task(
    self,
    connector_id: int,
    search_space_id: int,
    user_id: str,
):
    """Celery task for indexing DexScreener pairs."""
    try:
        return asyncio.run(
            _index_dexscreener_pairs(
                connector_id=connector_id,
                search_space_id=search_space_id,
                user_id=user_id,
            )
        )
    except Exception as e:
        logger.error(f"DexScreener indexing task failed: {str(e)}", exc_info=True)
        raise


async def _index_dexscreener_pairs(
    connector_id: int,
    search_space_id: int,
    user_id: str,
):
    """Async wrapper for DexScreener indexing."""
    async with get_async_session_context() as session:
        return await index_dexscreener_pairs(
            session=session,
            connector_id=connector_id,
            search_space_id=search_space_id,
            user_id=user_id,
        )
```

#### 2.3. Periodic Scheduler

**File**: `app/utils/periodic_scheduler.py`

**Add to existing mappings**:
```python
# Add to CONNECTOR_TYPE_TO_TASK_NAME
CONNECTOR_TYPE_TO_TASK_NAME = {
    # ... existing mappings
    SearchSourceConnectorType.DEXSCREENER_CONNECTOR: "index_dexscreener_pairs",
}

# Add import
from app.tasks.celery_tasks.connector_tasks import index_dexscreener_pairs_task

# Add to CONNECTOR_TYPE_TO_TASK
CONNECTOR_TYPE_TO_TASK = {
    # ... existing mappings
    SearchSourceConnectorType.DEXSCREENER_CONNECTOR: index_dexscreener_pairs_task,
}
```

#### 2.4. Routes Registration

**File**: `app/routes/__init__.py`

**Add**:
```python
# Add import
from app.routes.dexscreener_add_connector_route import router as dexscreener_add_connector_router

# Add to router includes (after other connector routes)
router.include_router(dexscreener_add_connector_router)
```

#### 2.5. Indexer Export

**File**: `app/tasks/connector_indexers/__init__.py`

**Add**:
```python
# Add import
from .dexscreener_indexer import index_dexscreener_pairs

# Add to __all__
__all__ = [
    # ... existing exports
    "index_dexscreener_pairs",
]
```

## 🔄 Usage Flow

### 1. Add Connector via API

```bash
curl -X POST "http://localhost:8000/api/connectors/dexscreener/add" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "space_id": 1,
    "tokens": [
      {
        "chain": "solana",
        "address": "So11111111111111111111111111111111111111112",
        "name": "Wrapped SOL"
      },
      {
        "chain": "ethereum",
        "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "name": "Wrapped ETH"
      }
    ]
  }'
```

### 2. Test Connection

```bash
curl -X GET "http://localhost:8000/api/connectors/dexscreener/test?chain=solana&token_address=So11111111111111111111111111111111111111112" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Trigger Manual Indexing

Indexing sẽ được trigger tự động qua:
- **Periodic scheduler**: Mỗi 60 phút (configurable)
- **Manual trigger**: Qua search_source_connectors_routes.py endpoint

### 4. Search Indexed Data

Data được index sẽ tự động available trong:
- AI Chat với context từ DexScreener
- Search results
- Document retrieval

## ⚠️ Important Considerations

### Rate Limiting
- DexScreener API: 300 requests/minute
- Với 50 tokens tracked, mỗi lần index = 50 requests
- Recommended indexing interval: **60 minutes**
- Implement exponential backoff nếu hit rate limit

### Data Freshness
- Crypto market data thay đổi nhanh
- Consider shorter intervals (15-30 min) cho high-priority tokens
- Implement priority queue cho important tokens

### Storage Optimization
- Mỗi pair = 1 document với chunks
- 50 tokens × 5 pairs average = 250 documents
- Monitor storage usage và implement cleanup cho old data

### Error Handling
- Network failures: Retry với exponential backoff
- API errors: Log và skip, không block toàn bộ indexing
- Invalid data: Validate trước khi index

## 🎯 Next Steps

1. **Implement Phase 1**: Core components (connector, indexer, DB schema)
2. **Test locally**: Verify API calls và data formatting
3. **Implement Phase 2**: Routes và integration
4. **Test end-to-end**: Add connector → Index → Search
5. **Deploy**: Monitor performance và adjust intervals
6. **Optimize**: Based on usage patterns và feedback

## 📊 Success Metrics

- ✅ Connector successfully fetches data from DexScreener API
- ✅ Data được format chính xác sang markdown
- ✅ Documents được index với proper chunks và embeddings
- ✅ Search results include DexScreener data
- ✅ AI Chat có context từ crypto market data
- ✅ Periodic indexing runs without errors
- ✅ Rate limits được respect

---

**Note**: Implementation này dựa trên:
- Official DexScreener API Documentation
- Existing Nowing connector patterns (Luma, Slack, etc.)
- Best practices từ production connectors
