story_key: 22-2-telegram-mtproto-userbot-client-encrypted-session-pool
status: done
baseline_commit: d1877927ca8681283e1858a7da054b1f413a9686
epic: 22
story: 2
---

# Story 22.2: Telegram MTProto Userbot Client, Encrypted Session Pool & Anti-Ban Cooldown

Status: done

<!-- Note: Governed by FR-71, FR-72, FR-73, AD-1 to AD-8, and Architecture Spine: epics.md (Epic 22) -->

## Story

As a system administrator and background worker,
I want to onboard Telegram phone accounts into encrypted `StringSession` records with distributed mutex locks and automatic `FloodWait` cooldowns,
So that Nowing workers can securely access private channels and deep discussion threads without risking account bans or session conflicts.

---

## Acceptance Criteria

### AC-1 — Admin Multi-Step OTP/2FA Account Onboarding
**Given** an admin supplying phone number, `api_id`, and `api_hash`,
**When** requesting OTP via `/api/admin/scraper-accounts/telegram/request-otp`,
**Then** Telethon sends a verification code, caches flow state in Redis (TTL=300s), and returns `otp_sent`.
**When** submitting code via `/api/admin/scraper-accounts/telegram/verify-otp`,
**Then** if 2FA is required, it returns `2fa_required`; otherwise it exports a `StringSession`, encrypts credentials using `TokenEncryption`, and saves a `ScraperPlatformAccount` record (`platform="telegram"`).
**When** submitting password via `/api/admin/scraper-accounts/telegram/verify-2fa`,
**Then** it completes login, exports `StringSession`, and saves the encrypted account record.

### AC-2 — In-Memory StringSession Lifecycle (Zero Disk Footprint)
**Given** an encrypted Telegram account in the database,
**When** a worker initializes `TelethonScraperClient.from_credentials()`,
**Then** it decrypts the session string and connects via `StringSession` in memory only without generating any `.session` SQLite files on disk.

### AC-3 — Redis Mutex Distributed Session Locking
**Given** an account being actively used by Worker A,
**When** Worker B attempts to acquire `TelegramSessionLock(account_id)`,
**Then** the Redis mutex (`SET telegram:session:lock:{account_id} val NX EX 120`) fails to acquire, preventing concurrent multi-worker session clashes on the same Telegram account.

### AC-4 — FloodWaitError Anti-Ban Backoff & Randomized Jitter Cooldown
**Given** a Telegram MTProto request failing with `FloodWaitError(seconds=N)`,
**When** the worker catches the error,
**Then** it calls `rotator.record_use(account, success=False, error_type="rate_limited")`, sets `banned_until = now + N + uniform(2, 5)`, releases the Redis lock, and rotates to an alternate available account without retrying immediately on the throttled session.

---

## Tasks / Subtasks

- [x] **Task 1: Telethon MTProto Client Wrapper (`nowing_backend/app/proprietary/platforms/telegram/client.py`)**
  - [x] Implement `TelethonScraperClient` using Telethon `StringSession`.
  - [x] Support SOCKS5 proxy configuration (`socks5h://`).
  - [x] Implement in-memory connection lifecycle without disk artifacts.

- [x] **Task 2: Redis Mutex Lock & Account Rotator (`nowing_backend/app/services/telegram_session_service.py`)**
  - [x] Implement `TelegramSessionLock` using Redis `SET key val NX EX 120`.
  - [x] Integrate with `ScraperPlatformAccountRotator` for health-aware account selection.
  - [x] Implement `FloodWaitError` handler with randomized jitter cooldown (`N + uniform(2, 5)`).

- [x] **Task 3: Admin OTP/2FA Onboarding Endpoints (`nowing_backend/app/routes/admin_scraper_platform_accounts_routes.py`)**
  - [x] `POST /api/admin/scraper-accounts/telegram/request-otp` (sends code, caches `phone_code_hash` in Redis).
  - [x] `POST /api/admin/scraper-accounts/telegram/verify-otp` (completes auth or requests 2FA password).
  - [x] `POST /api/admin/scraper-accounts/telegram/verify-2fa` (verifies cloud password and saves encrypted credentials).
  - [x] Provide CLI script `scripts/telegram_auth_helper.py` for terminal onboarding.

- [x] **Task 4: Automated Unit & Integration Tests**
  - [x] Unit tests for `TelethonScraperClient` initialization and proxy resolution.
  - [x] Unit tests for `TelegramSessionLock` acquisition, renewal, and release.
  - [x] Unit tests for `FloodWait` cooldown calculation with jitter.
  - [x] Integration tests for Admin OTP/2FA state machine.

### Review Findings

- [x] [Review][Patch] Fix handle_flood_wait cooldown overwriting by passing custom_cooldown_until to rotator.record_use [nowing_backend/app/services/telegram_session_service.py:127]
- [x] [Review][Patch] Raise TelegramSessionLockError in TelegramSessionLock.__aenter__ on acquire failure [nowing_backend/app/services/telegram_session_service.py:98]
- [x] [Review][Patch] Ensure TelethonScraperClient.disconnect() cleans up raw client even when disconnected [nowing_backend/app/proprietary/platforms/telegram/client.py:122]
- [x] [Review][Patch] Omit plain session_string from TelegramAuthResponse schema and endpoints [nowing_backend/app/schemas/scraper_platform_account.py:86]
- [x] [Review][Patch] Add lower bound and non-finite checks to calculate_flood_wait_cooldown [nowing_backend/app/services/telegram_session_service.py:29]
- [x] [Review][Patch] Sanitize and add scheme/port fallbacks in parse_proxy_url [nowing_backend/app/proprietary/platforms/telegram/client.py:20]
- [x] [Review][Patch] Strip whitespace from phone and code in Telegram OTP schemas [nowing_backend/app/schemas/scraper_platform_account.py:53]
- [x] [Review][Patch] Improve Vietnamese shorthand price extraction in TelegramEntityExtractor [nowing_backend/app/proprietary/platforms/telegram/entity_extractor.py:248]
- [x] [Review][Defer] Redundant column-level index=True on Telegram models with composite Index [nowing_backend/app/proprietary/platforms/telegram/models.py:54] — deferred, pre-existing

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
uv run pytest tests/unit/proprietary/platforms/telegram/test_client.py tests/unit/services/test_telegram_session_service.py -v

# 2. Run Telegram Admin Integration Tests
uv run pytest tests/integration/routes/test_admin_scraper_platform_accounts_telegram.py -v

# 3. Lint & Format
uv run ruff check app/proprietary/platforms/telegram app/services/telegram_session_service.py app/routes/admin_scraper_platform_accounts_routes.py
uv run ruff format app/proprietary/platforms/telegram app/services/telegram_session_service.py app/routes/admin_scraper_platform_accounts_routes.py
```

---

## Dev Notes

### ATDD Artifacts
- **Checklist:** `_bmad-output/test-artifacts/atdd-checklist-22-2-telegram-mtproto-userbot-client-encrypted-session-pool.md`
- **Unit Tests (Client):** `nowing_backend/tests/unit/proprietary/platforms/telegram/test_client.py` (5 passed)
- **Unit Tests (Session Lock):** `nowing_backend/tests/unit/services/test_telegram_session_service.py` (6 passed)
- **Integration Tests (Admin API):** `nowing_backend/tests/integration/routes/test_admin_scraper_platform_accounts_telegram.py` (5 passed)
- **Total:** 16 tests passed (100% green).
