# CI Secrets Checklist

## Required Repository Secrets

| Secret | Purpose | Used In |
| --- | --- | --- |
| `SLACK_WEBHOOK_URL` | Post failure notification to Slack | `.github/workflows/test.yml` |

## Optional Secrets

| Secret | Purpose |
| --- | --- |
| `PACT_BROKER_BASE_URL` | Contract testing broker URL (if enabling Pact) |
| `PACT_BROKER_TOKEN` | Contract testing broker token (if enabling Pact) |

## No Secrets in CI Files

- All API keys, tokens, and passwords are injected via `secrets.*` or service env blocks.
- No hardcoded credentials in `.github/workflows/test.yml`.
