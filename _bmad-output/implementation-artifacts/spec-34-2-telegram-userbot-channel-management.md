# Story 34.2 Spec: Web Admin Management Endpoints for Telegram Userbots & Monitored Channels

## Intent

As a Workspace Admin, I want a web management console for Telegram userbot sessions, channel lists, and ingest filters, so that I do not need terminal CLI commands to manage Telegram monitored channels.

## Acceptance Criteria

- **Given** the user navigates to `/dashboard/[workspace_id]/channels/telegram`, **When** requesting channel status, **Then** the frontend loads all active userbot sessions and allows toggling channel monitoring.
- **And** CRUD operations support adding channels, setting ingest filters, and updating poll intervals.

## Technical Design

### 1. API Endpoints

- `GET /api/v1/workspaces/{workspace_id}/channels/telegram` — list monitored channels + userbot session health
- `POST /api/v1/workspaces/{workspace_id}/channels/telegram` — add new Telegram channel to monitor
- `PATCH /api/v1/workspaces/{workspace_id}/channels/telegram/{target_id}/toggle` — toggle `is_active`
- `DELETE /api/v1/workspaces/{workspace_id}/channels/telegram/{target_id}` — remove channel from monitoring

### 2. Service Implementation

- `app/services/telegram_channel_service.py`:
  - List `SocialMonitoredTarget` where `platform == "telegram_channel"` and `workspace_id == ws_id`
  - Fetch active userbot session status via `telegram_session_service`
  - Create channel with validation (channel username or invite link)
  - Toggle monitoring status atomically

### 3. Safety Constraints

- Multi-tenant workspace isolation enforced via `RequirePermission(Permission.LEADS_WRITE)`
- Input validation on Telegram channel usernames / invite links
- Prevents duplicate channel additions per workspace
