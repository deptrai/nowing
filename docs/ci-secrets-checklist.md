# CI Secrets Checklist — Nowing

Configure these in: **GitHub → Repository Settings → Secrets and variables → Actions**

## Required

| Secret | Description | Required |
|--------|-------------|----------|
| `TEST_USER_EMAIL` | Email for E2E test account | ✅ Yes |
| `TEST_USER_PASSWORD` | Password for E2E test account | ✅ Yes |

Default test account locally: `test@nowing.test` / `Admin@Nowing1`

## Optional (Notifications)

| Secret | Description |
|--------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for failure alerts |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel ID for failure alerts |

If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` are not set, the notification step is silently skipped.

## Setup Steps

1. Go to `github.com/<org>/nowing/settings/secrets/actions`
2. Click **New repository secret** for each secret above
3. Push to `dev` branch to trigger first pipeline run
4. Verify all jobs appear green in the **Actions** tab

## Notes

- `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` must match a seeded account in the test database
- The CI database is ephemeral (`nowing_test`) — migrations run automatically on backend start
- Never commit real credentials to `.env` files tracked by git
