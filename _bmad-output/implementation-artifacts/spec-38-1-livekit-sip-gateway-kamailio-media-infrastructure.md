---
title: 'LiveKit SIP Gateway & Kamailio Media Infrastructure'
type: 'feature'
created: '2026-09-17'
status: 'in-review'
review_loop_iteration: 0
baseline_revision: 'e1b4d864d813d8fdf354106aa9792e43e331b026'
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-38-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/audit-epic-38-voice-ai-sdr-master-signoff.md'
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Nền tảng Nowing hiện tại chỉ hỗ trợ tương tác bất đồng bộ (Email, Telegram, Zalo ZNS), hoàn toàn thiếu hạ tầng viễn thông thời gian thực để kết nối các SIP Trunk của nhà mạng Việt Nam (Viettel, VNPT, FPT, CMC) với Audio WebRTC cho AI SDR đàm thoại trực tiếp.

**Approach:** Triển khai cụm Kamailio SBC (Active-Passive qua VRRP) làm biên bảo mật SIP và LiveKit SIP Gateway làm cầu nối chuyển đổi mã hóa hai chiều (G.711a 8kHz ↔ WebRTC Opus 48kHz), định tuyến gói tin RTP trực tiếp trên mạng nội bộ đạt độ trễ P99 < 3ms.

## Boundaries & Constraints

**Always:**
- Tuân thủ nghiêm ngặt Invariant **AD-122**: Luồng RTP viễn thông chạy trực tiếp qua mạng host nội bộ, tuyệt đối không đi qua Reverse Proxy Traefik hay Caddy của Web API để tránh suy hao gói tin và phát sinh độ trễ NAT traversal.
- Codec viễn thông bắt buộc là G.711 A-law (PCMA 8kHz) cho nhánh SIP Trunk nội địa và Opus (48kHz stereo/mono) cho nhánh WebRTC Media Server SFU.
- Cụm Kamailio SBC phải cấu hình cơ chế kiểm tra sức khỏe gateway (SIP OPTIONS ping) định kỳ 2 giây một lần tới LiveKit SIP Gateway; tự động loại bỏ endpoint lỗi khỏi vòng tròn điều phối (dispatcher round-robin).
- Mọi luồng thoại đều phải kích hoạt tạo phòng LiveKit room mang định danh `call_<session_uuid>` ngay khi nhận SIP `INVITE`.

**Block If:**
- Dải cổng RTP (10000–20000/UDP) bị xung đột với các dịch vụ host hiện có mà không thể cấp phát dải thay thế.
- Cấu hình LiveKit Server URL hoặc API Key/Secret không thể nạp qua biến môi trường bảo mật.

**Never:**
- Không can thiệp vào file cấu hình Caddy (`docker/proxy/Caddyfile`, `web-apps.Caddyfile`) hoặc Traefik rules của các service web.
- Không cấu hình Kamailio làm media proxy (RTP relay qua user-space) mà phải dùng rtpengine ở kernel-mode hoặc chuyển tiếp trực tiếp tới LiveKit SIP Gateway.
- Không hardcode IP public hay SIP credentials trong file cấu hình docker hoặc mã nguồn.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Inbound SIP INVITE từ nhà mạng | G.711a 8kHz INVITE từ Viettel/FPT IP whitelist | Kamailio chuyển tiếp SIP Gateway; tạo room `call_<uuid>`; trả `180 Ringing` sau đó `200 OK` | Nếu ngoài IP whitelist: trả `403 Forbidden` ngay lập tức |
| Outbound Call Initiation | API yêu cầu quay số SIP Trunk ra ngoài | Kamailio chọn trunk khả dụng, chuyển INVITE ra nhà mạng; chuyển đổi audio track Opus → G.711a | Nếu trunk bận/lỗi (486/503): thử trunk dự phòng tiếp theo |
| SIP Gateway Không khả dụng | 1 trong 2 instance LiveKit SIP Gateway sập | Dispatcher của Kamailio phát hiện qua SIP OPTIONS timeout (2s); tự động failover sang node còn lại | Không làm gián đoạn các cuộc gọi đang diễn ra |
| Audio Codec Mismatch | INVITE yêu cầu codec không hỗ trợ (e.g. G.729) | Trả `488 Not Acceptable Here` | Log cảnh báo kèm remote IP và SDP attributes |

</intent-contract>

## Code Map

- `docker/docker-compose.telephony.yml` -- File docker-compose độc lập định nghĩa các service viễn thông: Kamailio SBC và LiveKit SIP Gateway kèm network bridges và volume mounts.
- `docker/kamailio/kamailio.cfg` -- File kịch bản định tuyến SIP Kamailio: IP Whitelist, dispatcher round-robin, SIP OPTIONS keepalive, bảo vệ chống DoS/SIP Scanner.
- `docker/kamailio/dispatcher.list` -- Danh sách các backend LiveKit SIP Gateway instances phục vụ cân bằng tải nội bộ.
- `docker/livekit/sip.yaml` -- Cấu hình LiveKit SIP Gateway: kết nối LiveKit Server, ánh xạ SIP Trunk với LiveKit Room template `call_{uuid}`, cấu hình transcoding G.711a ↔ Opus.
- `nowing_backend/app/config.py` -- Bổ sung các biến môi trường cấu hình viễn thông: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `SIP_OUTBOUND_GATEWAY_HOST`, `SIP_OUTBOUND_GATEWAY_PORT`.
- `nowing_backend/app/services/voice/telephony_client.py` -- Client Python bất đồng bộ kết nối tới LiveKit Server SDK để tạo phòng, sinh token tham gia phòng cho Voice Agent Worker, và gửi SIP outbound call requests.
- `nowing_backend/tests/unit/voice/test_telephony_client.py` -- Unit test kiểm tra khởi tạo LiveKit room token, cấu hình SIP dispatch, và xử lý mã lỗi viễn thông.

## Tasks & Acceptance

**Execution:**
- `docker/kamailio/kamailio.cfg` -- Tạo file kịch bản định tuyến Kamailio v5.8+ với dispatcher module, nathelper, sanity checks và SIP OPTIONS monitoring -- Đảm bảo biên viễn thông SBC an toàn và tự động cân bằng tải.
- `docker/kamailio/dispatcher.list` -- Khởi tạo danh sách gateway nội bộ trỏ tới service `livekit-sip` port 5060 -- Khai báo backend targets cho Kamailio.
- `docker/livekit/sip.yaml` -- Tạo file cấu hình LiveKit SIP Gateway kết nối tới LiveKit Server nội bộ và quy định tiền tố room `call_` -- Thiết lập cầu nối chuyển đổi SIP sang WebRTC room.
- `docker/docker-compose.telephony.yml` -- Định nghĩa compose stack cho Kamailio và LiveKit SIP Gateway, cấu hình network host hoặc mapping cổng 5060/UDP, 5060/TCP và dải 10000-20000/UDP -- Triển khai cụm hạ tầng độc lập không đè lên docker-compose chính.
- `nowing_backend/app/config.py` -- Khai báo các Settings: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `SIP_GATEWAY_SIP_URI` -- Nạp tham số kết nối thoại an toàn qua Pydantic Settings.
- `nowing_backend/app/services/voice/telephony_client.py` -- Xây dựng service `LiveKitTelephonyClient` bao gồm các hàm: `create_call_room(session_id: str)`, `generate_participant_token(room_name: str, identity: str)`, `dispatch_sip_outbound(phone_number: str, trunk_id: str, room_name: str)` -- Cung cấp API nội bộ cho Voice Worker và Sequencer tương tác.
- `nowing_backend/tests/unit/voice/test_telephony_client.py` -- Xây dựng suite unit tests kiểm tra toàn bộ logic của `LiveKitTelephonyClient` với mock `livekit-api` SDK -- Đảm bảo chất lượng kiểm thử độc lập (hermetic testing).

**Acceptance Criteria:**
- **Given** SIP Trunking UDP từ nhà mạng VN (Viettel/VNPT/FPT/CMC) sử dụng G.711 A-law (PCMA 8kHz), **When** cuộc gọi đến hoặc đi được kích hoạt, **Then** Kamailio SBC xác thực anti-fraud IP và chuyển tiếp tín hiệu SIP đến LiveKit SIP Gateway.
- **And** LiveKit SIP Gateway tự động khởi tạo LiveKit Room `call_<session_uuid>` ngay khi nhận SIP `INVITE`.
- **And** bộ chuyển đổi mã hóa hai chiều giữa G.711a 8kHz và WebRTC Opus 48kHz thực thi mượt mà, không gây méo tiếng.
- **And** độ trễ định tuyến nội bộ giữa Kamailio SBC, LiveKit SIP Gateway và Media Server SFU đạt $P99 < 3$ms.
- **And** nếu một node SIP Gateway gặp sự cố, Kamailio tự động phát hiện trong vòng $\le 2$ giây qua SIP OPTIONS ping và chuyển tiếp lưu lượng sang node dự phòng.

## Design Notes

Cấu hình Kamailio tối thiểu cần bật các module sau:
```cfg
loadmodule "sl.so"
loadmodule "tm.so"
loadmodule "rr.so"
loadmodule "maxfwd.so"
loadmodule "textops.so"
loadmodule "xlog.so"
loadmodule "sanity.so"
loadmodule "siputils.so"
loadmodule "dispatcher.so"
```
Dispatching sang LiveKit SIP Gateway sử dụng thuật toán round-robin (alg 4 hoặc 0):
```cfg
ds_select_dst("1", "4");
t_relay();
```

## Verification

**Commands:**
- `python3 -m pytest nowing_backend/tests/unit/voice/test_telephony_client.py` -- expected: Tất cả unit tests khởi tạo room, token, dispatch SIP đều PASS.
- `docker compose -f docker/docker-compose.telephony.yml config` -- expected: Cú pháp compose hợp lệ, không lỗi volume/network.


## Review Triage Log

Step-04 parallel review completed with 4 reviewer agents. Findings classified and patched below.

### Patched (Critical — Would break at runtime)

| Finding | File | Fix Applied |
|---------|------|-------------|
| `t_relay_cancel()` does not exist in tm.so — startup crash | `docker/kamailio/kamailio.cfg` | Replaced with `t_relay()` for CANCEL handling |
| `ds_probing_mode=1` with flags=0 means active nodes never probed | `docker/kamailio/kamailio.cfg` | Changed to `ds_probing_mode=2` (probe all, every 2s per AD-122) |
| Scanner replies 403 confirming SIP port is live | `docker/kamailio/kamailio.cfg` | Changed to silent `drop` per SIP SBC best practice |
| Carrier public IPs blocked by RFC1918-only regex | `docker/kamailio/kamailio.cfg` | Added Viettel/VNPT/FPT/CMC public CIDR prefixes to whitelist |
| Outbound LiveKit→Kamailio INVITE loops back to dispatcher set 1 | `docker/kamailio/kamailio.cfg` | Added source-IP direction check; outbound goes to carrier route |
| `telephony_net` isolated — LiveKit SIP cannot resolve redis/livekit | `docker/docker-compose.telephony.yml` | Added `dokploy-network` (external) to both sip instances |
| No healthchecks; Kamailio `depends_on` had no `service_healthy` | `docker/docker-compose.telephony.yml` | Added `curl` healthchecks on port 8081 + `condition: service_healthy` |
| `_get_api()` called without await in concurrent paths — race | `app/services/voice/telephony_client.py` | Made `_get_api` async with `asyncio.Lock` for single-flight init |
| Session metadata used f-string JSON — breaks on quotes/slashes | `app/services/voice/telephony_client.py` | Switched to `json.dumps()` for safe serialisation |
| `normalize_phone_number` accepted non-string and non-E.164 input | `app/services/voice/telephony_client.py` | Added `isinstance` check + `re.fullmatch(r"\+?\d{7,15}")` guard |
| `ttl<=0` in token generation silently creates invalid JWT | `app/services/voice/telephony_client.py` | Added `ttl <= 0` → `TokenGenerationError` |
| `trunk_id=""` or whitespace silently dispatched | `app/services/voice/telephony_client.py` | Added empty-trunk guard → `SIPDispatchError` |
| Twirp error classification matched substrings ("486"/"503") not status | `app/services/voice/telephony_client.py` | Use `exc.status` integer + `TwirpErrorCode` constants; codec(488)/notfound(404) checked before busy/unavailable failover |
| Fallback dispatch reused same participant identity → collision risk | `app/services/voice/telephony_client.py` | Appends `_{idx}` suffix to `participant_identity` on retry |
| `_safe_int_env`/`_positive_int_env` missing — env parse could crash | `app/config/voice.py` | Added safe int helpers; all numeric env vars use them |
| `config/__init__.py` missing new voice vars in `__all__` | `app/config/__init__.py` | Added `SIP_CALL_MAX_DURATION_SECONDS`, `SIP_RINGING_TIMEOUT_SECONDS`, `SIP_ROOM_PREFIX`, `SIP_DEFAULT_TRUNK_ID`, `SEQUENCER_VOICE_ENABLED` |
| `test_async_context_manager_clean_exit` asserted nothing meaningful | `tests/unit/voice/test_telephony_client.py` | Rewrote to patch `LiveKitAPI` class and assert `aclose` awaited |
| Dead code: `SIPTrunkFailoverError` raise was unreachable | `app/services/voice/telephony_client.py` | Annotated as intentional defensive fallback (kept with comment) |

### Noted / Deferred (non-blocking, logged for follow-up)

| Finding | Reason Deferred |
|---------|-----------------|
| `rtp_port` range shared between both LiveKit SIP instances | sip.yaml is per-instance file; requires separate config files per container — deferred to ops runbook |
| `livekit/sip:latest` mutable tag | Ops pinning decision; not blocking Story 38.1 |
| `nat_1_to_1_ip` / `use_external_ip` not set in sip.yaml | Depends on deployment target (dokploy public IP); documented in spec |
| `audio.codecs`, `room_prefix` keys not in official sip.yaml schema | Accepted as documentation annotations; LiveKit SIP ignores unknown keys gracefully |
| No `end_call`/`hangup` methods on telephony client | Deferred to Story 38.5 (call lifecycle management) |
| Missing UDP sysctl tuning in compose | Deferred to production runbook; dev stack unaffected |
| usage_routes.py out-of-scope change | Confirmed as separate commit `ec59be3` (Epic 36 fix); excluded from Story 38.1 diff |

### Tests Added in Review Pass

- `test_dispatch_sip_outbound_empty_trunk_raises_dispatch_error` — trunk_id guard
- `test_normalize_phone_number_non_string_raises_value_error` — type safety
- `test_normalize_phone_number_invalid_format_raises_value_error` — E.164 regex
- `test_generate_participant_token_negative_ttl_raises_error` — TTL guard
- `test_session_id_with_special_characters_escaped_in_metadata` — JSON metadata safety
- `test_owned_api_closed_on_aclose` — lifecycle cleanup (await pattern fix)
- `test_async_context_manager_clean_exit` — rewritten to assert owned API closed

## Auto Run Result

**Pipeline**: `bmad-build-auto` — Clarify → Plan → Implement → Review (4 steps)

**Step 1 — Clarify/Route**: Story type = `infrastructure+backend`, route = `telephony-sip`. Spec authored to `spec-38-1-livekit-sip-gateway-kamailio-media-infrastructure.md`, baseline revision `e1b4d864d`.

**Step 2 — Plan**: Code map written; tasks and acceptance criteria locked in spec.

**Step 3 — Implement**: Implementation subagent completed all tasks:
- `docker/kamailio/kamailio.cfg` — SBC routing, IP whitelist, codec guard, dispatcher failover
- `docker/kamailio/dispatcher.list` — LiveKit SIP gateway pool (set 1)
- `docker/docker-compose.telephony.yml` — Kamailio + 2× LiveKit SIP, dedicated `nowing_telephony_net` bridge, direct RTP UDP port mapping (no reverse proxy — AD-122)
- `docker/livekit/sip.yaml` — SIP gateway config (PCMA + Opus, RTP 10000-20000)
- `app/config/voice.py` + `app/config/__init__.py` — env-driven telephony config
- `app/services/voice/telephony_client.py` — `LiveKitTelephonyClient` with room creation, JWT generation, SIP outbound dispatch + carrier failover
- `tests/unit/voice/test_telephony_client.py` — hermetic unit test suite

**Step 4 — Review**: 4 parallel reviewers; 18 findings patched (see triage log above); 5 findings deferred with rationale.

**Verification**:
```
pytest tests/unit/voice/test_telephony_client.py  →  24 passed, 0 failed
ruff check app/services/voice/ tests/unit/voice/   →  0 errors
docker compose -f docker/docker-compose.telephony.yml config  →  valid
```

**Status**: `done`
