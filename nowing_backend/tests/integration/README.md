# Integration Tests

Tests marked `@pytest.mark.integration` that require live external services.

## Two categories

| Category | Example | Requires |
|---|---|---|
| Database | `tests/integration/document_upload/` | Real PostgreSQL |
| Live APIs | `tests/integration/tools/` | Internet + optional API keys |

## Running API integration tests

```bash
# All crypto tool live API tests (serial — avoids rate limits)
uv run pytest -m integration tests/integration/tools/ -v -p no:xdist

# Single test
uv run pytest -m integration tests/integration/tools/test_crypto_tools_live.py::test_defillama_tvl_overview_returns_protocols -v -p no:xdist
```

> `-p no:xdist` disables parallel execution to respect external API rate limits.

## Environment variables (optional)

| Variable | Used by | Required? |
|---|---|---|
| `ETHERSCAN_API_KEY` | `get_contract_info` (ethereum) | For Etherscan calls |
| `BSCSCAN_API_KEY` | `get_contract_info` (bsc) | For BscScan calls |
| `POLYGONSCAN_API_KEY` | `get_contract_info` (polygon) | For Polygonscan calls |

Tests that need missing API keys return a graceful error and are skipped, not failed.

## Rate limits

| API | Limit | Notes |
|---|---|---|
| DeFiLlama | Unlimited (public) | Safe to call freely |
| CoinGecko | 30 req/min (free tier) | Add delay if running full suite |
| GoPlus | 2000 req/day | |
| CryptoPanic | Public tier | |
| Reddit | Public JSON | 429 on heavy usage |
| Etherscan | 5 calls/sec | Requires API key |

The `api_retry_delay` fixture in `conftest.py` adds 0.5s between tests.

## CI policy

Integration tests are **excluded from normal CI** (`-m "not integration"` in CI config).
Run them manually before merging stories that touch crypto tool implementations.
