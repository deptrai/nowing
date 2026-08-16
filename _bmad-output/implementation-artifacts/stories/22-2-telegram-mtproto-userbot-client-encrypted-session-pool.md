story_key: 22-2-telegram-mtproto-userbot-client-encrypted-session-pool
status: ready-for-dev
baseline_commit: d1877927ca8681283e1858a7da054b1f413a9686
epic: 22
story: 2
---

# Story 22.2: Telegram MTProto Userbot Client, Encrypted Session Pool & Anti-Ban Cooldown

Status: ready-for-dev

<!-- Note: Governed by FR-71, FR-72, FR-73, AD-1 to AD-8, and Architecture Spine: epics.md (Epic 22) -->

## Story

As a system administrator and background worker,
I want to onboard Telegram phone accounts into encrypted `StringSession` records with distributed mutex locks and automatic `FloodWait` cooldowns,
So that Nowing workers can securely access private channels and deep discussion threads without risking account bans or session conflicts.

---

## Acceptance Criteria

### AC-1 — Admin Multi-Step OTP/2FA Account Onboarding
**Given** an admin supplying phone number, `api_id`, and `api_hash`,
**When** calling `POST /api/admin/scraper-accounts/telegram/request-otp` or running `scripts/telegram_auth_helper.py`,
**Then** Telegram sends an authentication code, and the backend stores `phone_code_hash` and temporary session string in Redis (`telegram:auth_flow:{phone}`, TTL=300s).
**And** upon calling `POST /api/admin/scraper-accounts/telegram/verify-otp` with valid OTP:
  - If 2FA password is required, returns HTTP 200 with `status: "2fa_required"`.
  - Upon calling `POST /api/admin/scraper-accounts/telegram/verify-2fa` with Cloud Password, `TelethonScraperClient` exports a `StringSession`, encrypts it using `TokenEncryption(config.SECRET_KEY)`, and persists it in `scraper_platform_accounts.encrypted_credentials` with `platform="telegram"`.

### AC-2 — In-Memory Ephemeral MTProto Client & SOCKS5 Proxy Routing
**Given** an authorized `ScraperPlatformAccount` record,
**When** a worker initializes `TelethonScraperClient.from_credentials(credentials)`,
**Then** the session string is decrypted exclusively in memory and connected over MTProto via SOCKS5 proxy (`socks5h://` with remote DNS resolution).
**And** zero `.session` files or sqlite database artifacts are written to the container disk.

### AC-3 — Distributed Redis Mutex Lock on Account Pool
**Given** multiple enabled Telegram accounts in `scraper_platform_accounts`,
**When** `ScraperPlatformAccountRotator.get_credentials(platform="telegram")` is requested across distributed Celery workers,
**Then** it acquires a Redis distributed mutex lock `telegram:session:lock:{account_id}` (TTL 120s), preventing concurrent multi-worker session clashes on the same account.

### AC-4 — FloodWait Cooldown State Machine & Smooth Account Rotation
**Given** Telegram API raises `FloodWaitError(seconds=N)` during an MTProto operation,
**When** the worker catches the error,
**Then** it calls `rotator.record_use(account, success=False, error_type="rate_limited")`, sets `banned_until = now + N + uniform(2, 5)`, releases the Redis lock, and rotates to an alternate available account without retrying immediately on the throttled session.

---

## Tasks / Subtasks

- [ ] **Task 1: Telethon MTProto Client Wrapper (`nowing_backend/app/proprietary/platforms/telegram/client.py`)**
  - [ ] Implement `TelethonScraperClient` using Telethon `StringSession`.
  - [ ] Support SOCKS5 proxy configuration (`socks5h://`).
  - [ ] Implement in-memory connection lifecycle without disk artifacts.

- [ ] **Task 2: Redis Mutex Lock & Account Rotator (`nowing_backend/app/services/telegram_session_service.py`)**
  - [ ] Implement `TelegramSessionLock` using Redis `SET key val NX EX 120`.
  - [ ] Integrate with `ScraperPlatformAccountRotator` for health-aware account selection.
  - [ ] Implement `FloodWaitError` handler with randomized jitter cooldown (`N + uniform(2, 5)`).

- [ ] **Task 3: Admin OTP/2FA Onboarding Endpoints (`nowing_backend/app/routes/admin_scraper_platform_accounts_routes.py`)**
  - [ ] `POST /api/admin/scraper-accounts/telegram/request-otp` (sends code, caches `phone_code_hash` in Redis).
  - [ ] `POST /api/admin/scraper-accounts/telegram/verify-otp` (completes auth or requests 2FA password).
  - [ ] `POST /api/admin/scraper-accounts/telegram/verify-2fa` (verifies cloud password and saves encrypted credentials).
  - [ ] Provide CLI script `scripts/telegram_auth_helper.py` for terminal onboarding.

- [ ] **Task 4: Automated Unit & Integration Tests**
  - [ ] Unit tests for `TelethonScraperClient` initialization and proxy resolution.
  - [ ] Unit tests for `TelegramSessionLock` acquisition, renewal, and release.
  - [ ] Unit tests for `FloodWait` cooldown calculation with jitter.
  - [ ] Integration tests for Admin OTP/2FA state machine.

---

## Dev Agent Guardrails & Architectural Invariants

- **AD-1 (No Disk Session Files):** Bắt buộc dùng `StringSession` trong memory, cấm tạo file `.session` trên disk.
- **AD-2 (Redis Mutex Lock):** Mỗi tài khoản chỉ được phép có 1 worker active tại một thời điểm (`telegram:session:lock:{id}`).
- **AD-3 (FloodWait Backoff):** Bắt buộc tôn trọng `FloodWaitError` và cộng thêm jitter 2-5 giây.

---

## Verification Commands

```bash
# 1. Run Telegram Session & Client Unit Tests
cd nowing_backend
uv run pytest tests/unit/platforms/telegram/test_client.py tests/unit/platforms/telegram/test_session_lock.py -q

# 2. Lint & Format
ruff check app/proprietary/platforms/telegram app/services/telegram_session_service.py
ruff format app/proprietary/platforms/telegram app/services/telegram_session_service.py
```
