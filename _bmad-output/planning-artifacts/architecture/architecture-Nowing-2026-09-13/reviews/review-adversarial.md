# Adversarial Architecture Review: Nowing <-> XActions Connection Spine

**Target:** `/Users/luisphan/Documents/GitHub/nowing/_bmad-output/planning-artifacts/architecture/architecture-Nowing-2026-09-13/ARCHITECTURE-SPINE.md`  
**Date:** 2026-09-13  
**Reviewer:** Adversarial Architecture Auditor (Brownfield Grounded)  

---

## Verdict

**REJECTED (REQUIRES STRUCTURAL HARDENING):** Architecture Spine mang định hướng control/data plane đúng đắn nhưng chứa 4 lỗ hổng Critical và 4 lỗ hổng High khiến hai bên độc lập tuân thủ 100% văn bản AD vẫn build ra hệ thống gãy kết nối hoàn toàn: 100% event stream bị drop do lệch schema/casing, toàn bộ database records bị từ chối do mất multi-tenant context, Celery worker crash sau task đầu tiên do vòng đời event loop, và logic Lead extraction bị tê liệt do thiếu payload content.

---

## Findings Summary Matrix

| ID | Severity | Area | Conflict Core |
|---|---|---|---|
| **C1** | Critical | Stream Payload Contract | CamelCase vs Snake_case field mismatch; Pydantic ValidationError drops 100% events |
| **C2** | Critical | Multi-Tenancy Context | XActions thin event lacks `target_id`/`workspace_id`; DB drops all unowned records |
| **C3** | Critical | Data Plane Dereferencing | Thin pointer has no `content`; worker extraction yields 0 leads and 0.0 fit scores |
| **C4** | Critical | Client Lifecycle in Runtime | AD-5 proc-scoped singleton crashes on Celery `run_async_celery_task` loop teardown |
| **H1** | High | Control Plane RPC Schema | Flat vs nested `args` in `x_scrape`; parameter stripping or schema validation failure |
| **H2** | High | Ingestion Split-Brain | Dual data path (MCP response vs Redis Stream) causes race conditions or idle worker |
| **H3** | High | Multi-Domain Return Shape | Non-social crawlers return entity dicts (`jobs`, `products`); adapter parser drops all items |
| **H4** | High | Governor & Multi-Workspace | Global 15 burst / 60 RPM on `nowing` causes inter-workspace starvation via Celery beat |
| **M1** | Medium | Checkpoint Semantic Inversion | ACL `lastCursor` resumes backward in history; periodic monitoring starves of fresh delta posts |
| **M2** | Medium | Crawler StoreBatch Gap | Non-social crawlers (Shopee, etc.) omit `storeBatch`; stream hook never fires |
| **M3** | Medium | Discovery Taxonomy Mismatch | Compound platform keys in Nowing vs atomic descriptors in XActions break dynamic mapping |
| **M4** | Medium | Error Policy Coupling | Adapter mapping table cannot mutate Celery tasks or DB models without layering violation |
| **L1** | Low | Documentation Invariant | Spine specifies `UNIQUE(platform, external_post_id)` while DB requires `workspace_id` |
| **L2** | Low | Stream Trimming Divergence | AD-3 specifies MAXLEN ~1M while existing adapter uses 20,000; memory unbounded |

---

## Detailed Findings

### CRITICAL FINDINGS

#### Finding C1: Stream Payload Contract Mismatch (Wire Casing & Required Fields)
- **Lỗ hổng:**
  AD-3 định nghĩa thin event do XActions emit: `{id, platform, externalId, category, authorId, crawledAt, storageRef, scraperId}` (sử dụng camelCase chuẩn JavaScript/Node.js).
  Trong khi đó, Nowing consumer (`app/tasks/social_stream_worker.py`, lines 51-80) định nghĩa `SocialPostEvent(BaseModel)` với `extra="ignore"`, yêu cầu bắt buộc:
  - `platform: str`
  - `external_post_id: str` (không có default value, không có `validation_alias` hoặc alias)
  - `author_id: str | None = None`
  - `published_at: datetime | str | None = None`
  - `storage_ref: str | None = None`
  - `scraper_id: str | None = None`
- **Hai Unit minh họa:**
  - *Unit A (XActions AbstractCrawler):* Tuân thủ AD-3, sau `storeBatch` thực hiện `xAdd` vào `stream:social:raw_posts` với payload:
    `{"id": "fb_123", "platform": "facebook", "externalId": "100200300", "category": "social", "authorId": "usr_1", "crawledAt": "2026-09-13T10:00:00Z", "storageRef": "fb_123"}`.
  - *Unit B (Nowing social_stream_worker):* Nhận message từ Redis. `SocialPostEvent.model_validate(payload)` được gọi. Vì payload có `externalId` thay vì `external_post_id`, Pydantic loại bỏ `externalId` (do `extra="ignore"`) và báo lỗi `ValidationError: Field required: external_post_id`.
  Hàm `process_social_post_event` bắt `ValidationError`, log warning `"Invalid social post event"` và return `None`. Message bị ACK và đưa vào DLQ hoặc biến mất.
- **Hậu quả:** 100% message đẩy lên Redis Stream bị consumer vứt bỏ ngay lập tức.
- **Đề xuất siết AD:**
  - Bổ sung vào **AD-3 Rule:** Khóa chặt schema của Redis Stream payload bằng chuẩn snake_case thống nhất giữa hai hệ thống:
    Payload bắt buộc gồm: `{"id": str, "platform": str, "external_post_id": str, "category": str, "author_id": str, "crawled_at": str, "storage_ref": str, "scraper_id": str}`.
  - Cập nhật Nowing `SocialPostEvent` hỗ trợ `validation_alias=AliasChoices("external_post_id", "externalId")` và `storage_ref` / `storageRef` để phòng thủ hai đầu.

---

#### Finding C2: Mất hoàn toàn Multi-Tenant Context (`target_id`, `workspace_id`) khiến Post không thể ghi DB
- **Lỗ hổng:**
  AD-4 cấm Nowing adapter ghi vào stream (`adapter_v2.ingest_raw_post_to_stream` bị loại bỏ) và chỉ định XActions là SOLE WRITER.
  AD-3 quy định thin event chỉ gồm 8 trường kỹ thuật của scraper.
  Tuy nhiên, cơ sở dữ liệu của Nowing (`app/models/leads/social.py`, line 90 và `app/tasks/social_stream_worker.py`, lines 275-295) yêu cầu:
  - Cột `social_posts.workspace_id` là `NOT NULL` với `ForeignKey("workspaces.id")`.
  - Khóa trùng lặp `UniqueConstraint("workspace_id", "platform", "external_post_id")`.
  - Code `process_social_post_event` kiểm tra:
    ```python
    if target_id is None:
        logger.warning("Cannot persist social post %s/%s: target_id is missing", ...)
        return None
    if workspace_id is None:
        target = await session.get(SocialMonitoredTarget, target_id)
        if isinstance(target, SocialMonitoredTarget) and target.workspace_id:
            workspace_id = target.workspace_id
    if workspace_id is None:
        logger.warning("Cannot persist social post %s/%s: workspace_id is missing", ...)
        return None
    ```
- **Hai Unit minh họa:**
  - *Unit A (XActions AbstractCrawler):* Crawl dữ liệu và ghi vào Redis Stream với đúng 8 trường theo AD-3. XActions hoàn toàn không biết `target_id` hay `workspace_id` trong Postgres của Nowing là gì.
  - *Unit B (Nowing social_stream_worker):* Đọc event từ Redis Stream. Trường `target_id` là `None`, `workspace_id` là `None`. Consumer không thể xác định bài viết thuộc tenant/workspace nào, ghi log warning và hủy bỏ bản ghi (`return None`).
- **Hậu quả:** Dữ liệu crawl về thành công 100% nhưng không thể lưu vào cơ sở dữ liệu Nowing. Toàn bộ bài viết bị drop trong im lặng.
- **Đề xuất siết AD:**
  - Bổ sung vào **AD-2 Rule:** `x_scrape` bắt buộc nhận thêm metadata ngữ cảnh: `context: { "targetId": int/str, "workspaceId": int }`.
  - Bổ sung vào **AD-3 Rule:** `AbstractCrawler` phải truyền thụ động `context.targetId` (dưới tên `target_id`) và `context.workspaceId` (dưới tên `workspace_id`) vào payload của thin event trên Redis Stream. Nếu không có context (ví dụ crawl ad-hoc từ CLI), cho phép `target_id: null, workspace_id: null`.

---

#### Finding C3: Phantom Payload / Ghost Content — Tê liệt Pipeline Entity Extraction & Lead Creation
- **Lỗ hổng:**
  Spine khẳng định nguyên tắc tại Consistency Conventions:
  *"Thin pointer `{id,platform,externalId,category,authorId,crawledAt,storageRef,scraperId}`; payload đầy đủ lấy từ `storageRef`/artifact — không nhồi content vào stream."*
  Đồng thời, phần "Deferred" ghi nhận:
  *"Artifact delivery mechanism (Q1): shared volume `XACTIONS_ARTIFACT_ROOT` hay presigned URL — chốt khi biết topo deploy prod."*
  Tuy nhiên, tại Nowing consumer (`app/tasks/social_stream_worker.py`, lines 240-255):
  ```python
  extractor = SocialEntityExtractor()
  extracted = extractor.extract_all(event.content)
  intent_tag = extracted["intent"]
  fit_score = compute_fit_score(extracted, intent_tag, event.reactions_count, event.comments_count)
  ```
  Consumer lấy trực tiếp `event.content` để trích xuất số điện thoại, email, địa chỉ, giá cả, tính intent và fit score. Consumer **hoàn toàn không có code dereference `storageRef`**.
- **Hai Unit minh họa:**
  - *Unit A (XActions AbstractCrawler):* Tuân thủ AD-3, chỉ emit con trỏ mỏng không có `content` (hoặc `content` rỗng), gán `storageRef = "fs:/tmp/xactions/posts/123.json"`.
  - *Unit B (Nowing social_stream_worker):* Parse `event.content` rỗng (`""`). `SocialEntityExtractor` trả về 0 phone, 0 email, intent = `"other"`. `fit_score` luôn bằng `0.0`. Điều kiện `if intent_tag in SOCIAL_LEAD_INTENTS` không bao giờ thỏa mãn.
- **Hậu quả:** Bản ghi lưu vào `social_posts` có nội dung rỗng. Không có bất kỳ CRM `Lead` nào được tạo ra. Mục tiêu kinh doanh cốt lõi của việc tích hợp mạng xã hội bị tê liệt hoàn toàn.
- **Đề xuất siết AD:**
  - Sửa đổi **AD-3 Rule & Consistency Conventions:** Thin event trên Redis Stream bắt buộc phải mang trường `content_snippet` (hoặc `content` đầy đủ nếu độ dài <= 4000 ký tự) cùng `author_name` và `post_url`. Redis Stream sinh ra để xử lý throughput cao; việc nhồi chuỗi text ngắn vài KB vào Redis Stream hiệu quả hơn gấp hàng chục lần so với việc bắt worker gọi HTTP/FS dereference cho từng event đơn lẻ.
  - Trường `storage_ref` chỉ dùng làm con trỏ lưu trữ raw payload phục vụ backup/audit hoặc dataset > 100 records theo kiến trúc Artifact plane.

---

#### Finding C4: Vòng đời Client MCP bị phá hủy bởi cơ chế Event Loop của Celery Worker
- **Lỗ hổng:**
  AD-5 quy định:
  *"Persistent shared `XActionsMcpClient` per worker ... Rule: proc-scoped singleton (`get_client()`), initialize 1 lần, keep-alive; call_tool stateless".*
  Trong khi đó, runtime thực tế của Nowing (`app/tasks/celery_tasks/__init__.py`, lines 115-165) định nghĩa chuẩn thực thi mọi async Celery task qua hàm `run_async_celery_task`:
  ```python
  def run_async_celery_task[T](coro_factory: Callable[[], Awaitable[T]]) -> T:
      loop = asyncio.new_event_loop()
      asyncio.set_event_loop(loop)
      try:
          ...
          return loop.run_until_complete(coro_factory())
      finally:
          ...
          loop.close()
  ```
  Mỗi lần Celery task chạy, một `asyncio.AbstractEventLoop` mới được khởi tạo và bị **đóng (`loop.close()`) ngay khi task kết thúc** để dọn dẹp các connection pool của `asyncpg`.
- **Hai Unit minh họa:**
  - *Unit A (Task 1 - ingest_social_target_task):* Gọi `get_client()`. Client khởi tạo `streamablehttp_client`, bind session và transport vào Event Loop của Task 1. Task 1 hoàn thành, loop của Task 1 bị đóng (`loop.close()`).
  - *Unit B (Task 2 - ingest_social_target_task chạy sau đó trên cùng worker process):* Nhận lại instance singleton `XActionsMcpClient`. Task 2 gọi `client.call_tool(...)` trên Event Loop mới của Task 2. Session MCP cố gắng sử dụng stream/connection gắn với loop cũ đã bị đóng.
  Python ném ngoại lệ nghiêm trọng: `RuntimeError: Event loop is closed` hoặc `RuntimeError: Task <...> attached to a different loop`.
- **Hậu quả:** Celery worker chạy thành công đúng 1 task đầu tiên, sau đó vĩnh viễn crash ở tất cả các task tiếp theo cho đến khi tiến trình worker bị khởi động lại.
- **Đề xuất siết AD:**
  - Sửa đổi **AD-5 Rule:** Loại bỏ khái niệm "proc-scoped singleton trần". Định nghĩa `XActionsMcpClientPool` gắn theo vòng đời của Event Loop hiện hành (`loop-scoped client cache` hoặc thread-local loop check):
    ```python
    # Rule kiểm tra loop trước khi dùng
    if client._loop is None or client._loop.is_closed():
        client.reconnect_on_loop(asyncio.get_running_loop())
    ```
  - Hoặc cấu hình Celery worker sử dụng persistent event loop runner chuyên dụng cho queue connectors.

---

### HIGH FINDINGS

#### Finding H1: Xung đột cấu trúc tham số `args` phẳng (Flat) vs lồng nhau (Nested) trong `x_scrape`
- **Lỗ hổng:**
  AD-2 quy định: `x_scrape` nhận `{platform, action, args, accountId?, proxyUrl?, dryRun?}`. Ở đây `args` là một object lồng nhau (nested dictionary).
  Tuy nhiên, trong code Nowing hiện tại (`app/proprietary/platforms/xactions/adapter_v2.py`, lines 40-75):
  ```python
  "chotot_category": {
      "tool": "x_scrape",
      "args_builder": lambda t: {"platform": "chotot", "action": "posts", "category": t.target_id},
  },
  "shopee_keyword": {
      "tool": "x_scrape",
      "args_builder": lambda t: {"platform": "shopee", "action": "search", "keyword": t.target_id},
  }
  ```
  Nowing đang build tham số phẳng (flat), nơi `category` và `keyword` là sibling của `platform` và `action`.
- **Hai Unit minh họa:**
  - *Unit A (XActions server.js):* Implement schema `x_scrape` theo AD-2, yêu cầu `args: { type: "object" }`. Handler đọc `const { platform, action, args } = params; return scrape(platform, action, args);`.
  - *Unit B (Nowing adapter_v2.py):* Gửi `{ "platform": "shopee", "action": "search", "keyword": "laptop", "dryRun": false }`.
  Server MCP kiểm tra schema thấy thiếu trường bắt buộc `args` -> ném lỗi `XACT_4001: Invalid arguments (missing args)`. Hoặc server lấy `params.args` nhận `undefined`, gọi `scrape("shopee", "search", undefined)` -> Scraper chạy không có keyword tìm kiếm.
- **Hậu quả:** Toàn bộ các lệnh scrape gửi qua `x_scrape` bị lỗi schema hoặc mất tham số lọc.
- **Đề xuất siết AD:**
  - Chuẩn hóa **AD-2 Rule:** Quy định rõ `x_scrape` chấp nhận cấu trúc phẳng linh hoạt hoặc bắt buộc nested đồng bộ cả hai phía:
    Cấu trúc khuyến nghị:
    `x_scrape({ platform: string, action: string, args: Record<string, any>, accountId?: string, proxyUrl?: string, dryRun?: boolean })`.
  - Cập nhật toàn bộ `args_builder` trong `adapter_v2.py` để đóng gói target args vào key `"args"`:
    `lambda t: {"platform": "chotot", "action": "posts", "args": {"category": t.target_id}}`.

---

#### Finding H2: Split-Brain Ingestion — Xung đột hai đường truyền dữ liệu (MCP Response vs Redis Stream)
- **Lỗ hổng:**
  Spine nêu nguyên tắc: *"lệnh đi MCP, data đi stream"*.
  Tuy nhiên, `scrape()` trong XActions là hàm đồng bộ (blocking) trả về kết quả mảng items, và MCP `x_scrape` đóng gói mảng này vào `result.data`.
  Trong `social_xactions_ingest.py` (lines 180-210), Celery task `ingest_social_target`:
  1. Await `adapter.fetch_posts_for_target(target)`.
  2. Hàm này parse `result.data` từ MCP response.
  Nếu AD-4 loại bỏ bước Nowing ghi vào stream, thì Celery task này sẽ làm gì với `posts` nhận được từ MCP?
  Nếu Celery task tự lưu `posts` vào database, trong khi `AbstractCrawler` ở XActions cũng vừa bắn các posts đó vào Redis Stream -> `social_stream_worker` cũng đọc và UPSERT:
  Hai worker chạy song song cùng insert/update một bài viết, dẫn đến race condition tại logic tính Lead và gửi Alert (`_create_lead_from_social_post` và `_evaluate_alerts_for_social_post`).
  Ngược lại, nếu Celery task chỉ gọi MCP rồi vứt bỏ `result.data`: thì việc `x_scrape` giữ connection HTTP chờ crawler cào xong hàng trăm items là lãng phí tài nguyên và dễ dính HTTP timeout (mặc định 60s).
- **Hai Unit minh họa:**
  - *Unit A (XActions Scraper):* Chạy crawl 25 bài Facebook. Ghi 25 bài vào Redis Stream, đồng thời trả 25 bài trong `result.data` qua MCP response.
  - *Unit B (Nowing):* Celery task `ingest_social_target` nhận 25 bài từ MCP; cùng lúc Celery worker `process_social_stream` nhận 25 bài từ Redis. Cả hai cùng thực thi `LeadAssignmentService.assign_leads_batch`, gây duplicate email alert và phân bổ lead trùng lặp.
- **Hậu quả:** Race condition, duplicate business actions (Alert, Lead notification), hoặc timeout kết nối MCP.
- **Đề xuất siết AD:**
  - Bổ sung vào **AD-2 & AD-4 Rule:** Xác định rõ ngữ nghĩa phản hồi của `x_scrape` khi chế độ streaming bật (`REDIS_STREAM_ENABLED=true`):
    `x_scrape` trên control-plane chỉ trả về execution summary:
    `{ success: true, meta: { totalCrawled: 25, streamKey: "stream:social:raw_posts", durationMs: 4200 }, data: [] }`.
    `social_xactions_ingest` chỉ chịu trách nhiệm trigger và cập nhật `target.last_scraped_at`, tuyệt đối không xử lý dữ liệu từ MCP response. Toàn bộ dữ liệu đi duy nhất qua Data plane (Redis Stream).

---

#### Finding H3: Scraper các domain phi Social trả về Entity Object (`jobs`, `products`, `listings`) gây vỡ Parser
- **Lỗ hổng:**
  Spine mở rộng scope ra 9 domain: ecom, realestate, recruitment, procurement, v.v. (AD-SOC-9).
  Nhưng các crawler hiện có trong XActions không trả về mảng post đồng nhất:
  - TopCV (`src/scrapers/recruitment/topcv/crawler.js`, line 113): trả về `{ jobs: [...], pageInfo: {...} }`.
  - Shopee (`src/scrapers/ecom/shopee/crawler.js`, line 160): trả về `{ products: [...], pageInfo: {...} }`.
  - Batdongsan (`src/scrapers/realestate/batdongsan/crawler.js`, line 160): trả về `{ listings: [...], pageInfo: {...} }`.
  - Masothue (`src/scrapers/procurement/masothue/crawler.js`, line 148): trả về `{ results: [...] }` hoặc `{ post: {...} }`.
  Trong khi đó, `adapter_v2.py` (lines 145-155) giả định `result.get("data")` luôn là một `list[dict]`:
  ```python
  data = result.get("data", [])
  posts = []
  for item in data:
      if not isinstance(item, dict):
          continue
      posts.append(SocialPostData(...))
  ```
- **Hai Unit minh họa:**
  - *Unit A (TopCV Crawler):* Trả về `{ jobs: [ { id: "job_1", title: "Dev" } ] }`.
  - *Unit B (Nowing adapter_v2.py):* Nhận dict. `for item in data` sẽ lặp qua các keys của dict (`"jobs"`, `"pageInfo"`). Biến `item` là `str`. Dòng `if not isinstance(item, dict): continue` bỏ qua toàn bộ keys. Kết quả trả về `posts = []`.
- **Hậu quả:** 100% các domain mới (TopCV, Shopee, Batdongsan, Masothue) trả về dữ liệu rỗng khi gọi qua adapter của Nowing.
- **Đề xuất siết AD:**
  - Bổ sung vào **AD-2 & AD-3 Rule:** Quy định chuẩn Envelope Canonical Data Transformation.
    Trong `x_scrape` dispatcher và `AbstractCrawler.storeBatch`, mọi item thuộc mọi domain phải được chuẩn hóa qua một adapter mapper chung:
    Mỗi entity đều phải có view chuẩn: `id`, `externalId`, `title`, `content` (description/summary), `authorId` / `authorName`, `url`, `publishedAt`, kèm `raw_payload` giữ nguyên domain fields.
    Nếu trả về envelope, `data` bắt buộc là một Array phẳng `NormalizedItem[]`, metadata phân trang đưa vào `meta.pageInfo`.

---

#### Finding H4: Thundering Herd & Nghẽn Quota giữa các Workspace do gộp chung Consumer Quota
- **Lỗ hổng:**
  AD-8 quy định: Mọi call từ Nowing đều gắn `X-Consumer-Id: nowing`. XActions Rate Governor áp quota tĩnh: `rpmLimit: 60`, `burstLimit: 15`.
  AD-8 yêu cầu: *"Throttle theo workspace do nowing tự giới hạn trước khi gọi — không dựa vào XActions per-user quota."*
  Tuy nhiên, trong Nowing (`app/tasks/celery_tasks/social_xactions_ingest.py`, lines 225-260), scheduler `check_social_monitored_targets_task` chạy mỗi phút:
  Quét toàn bộ target của TẤT CẢ các workspace đến hạn cào và đẩy đồng loạt vào Celery (`ingest_social_target_task.delay(target.id)`).
  Nowing **hoàn toàn không có cơ chế client-side rate limiter / token bucket** theo workspace trước khi gọi MCP.
- **Hai Unit minh họa:**
  - *Unit A (Workspace X có 20 targets):* Đến chu kỳ 15 phút, 20 task Celery của Workspace X kích hoạt đồng thời, gửi 20 HTTP requests với `X-Consumer-Id: nowing`.
  - *Unit B (Workspace Y có 1 target quan trọng):* Gửi request thứ 21 cùng thời điểm.
  XActions Governor chỉ cho phép burst 15 requests, 6 requests còn lại (bao gồm cả request của Workspace Y) bị từ chối ngay với mã lỗi `XACT_4291` (Rate Limited).
- **Hậu quả:** Hiện tượng "Noisy Neighbor" — một workspace nhiều target sẽ làm sập quota của toàn bộ các workspace khác trong hệ thống Nowing. Các task bị retry dồn toa gây bão request (thundering herd).
- **Đề xuất siết AD:**
  - Bổ sung vào **AD-8 Rule:**
    1. Ở phía Nowing: Bắt buộc cấu hình Celery rate limit trên queue `connectors` (ví dụ `rate_limit="30/m"`) hoặc sử dụng Redis Token Bucket trước khi dispatch MCP call.
    2. Ở phía XActions: Cho phép header phụ `X-Workspace-Id: <id>`. `AdaptiveRateGovernor` duy trì quota con per-workspace (ví dụ mỗi workspace tối đa 10 RPM, burst 3) bên cạnh global consumer ceiling để chống độc quyền tài nguyên.

---

### MEDIUM FINDINGS

#### Finding M1: Nghịch đảo ngữ nghĩa Checkpoint (Forward Crawl vs Backward Resume)
- **Lỗ hổng:**
  AD-9 cấm Nowing truyền cursor và giao phó toàn bộ cho ACL (Auto Checkpoint Lookup) của XActions.
  Trong XActions `base-crawler.js` (lines 450-465), ACL tìm checkpoint cũ và tự động inject `[cursorField] = checkpoint.lastCursor`.
  Trong pagination của hầu hết mạng xã hội (Twitter, Facebook, Mastodon): `cursor` hoặc `max_id` dùng để cuộn trang ngược về quá khứ (lấy bài cũ hơn).
  Khi Nowing chạy Celery định kỳ 15 phút một lần để cào "bài mới phát sinh", việc tự động nhồi `lastCursor` (vốn là con trỏ của bài cũ nhất ở đợt cào trước) sẽ khiến crawler tiếp tục cào sâu hơn vào quá khứ thay vì cào các bài viết mới xuất hiện ở đầu feed.
- **Hai Unit minh họa:**
  - *Unit A (Nowing Scheduler):* Chạy lúc 10:00 (cào 20 bài mới nhất), checkpoint lưu cursor bài thứ 20. Đến 10:15, scheduler kích hoạt crawl mới để tìm bài đăng từ 10:00 - 10:15.
  - *Unit B (XActions ACL):* Tự động lấy `lastCursor` của đợt 10:00 đưa vào args. Crawler bắt đầu tải từ bài thứ 21 trở về trước (lịch sử cũ). Toàn bộ bài đăng mới trong khoảng 10:00 - 10:15 bị bỏ qua hoàn toàn.
- **Hậu quả:** Hệ thống giám sát thời gian thực bị mù thông tin mới, chỉ cào lặp lại lịch sử cũ.
- **Đề xuất siết AD:**
  - Sửa đổi **AD-9 Rule:** Phân định rõ 2 chế độ crawl trong `x_scrape`:
    - `mode: "delta"` (mặc định cho scheduled monitor): Không áp dụng `lastCursor` lùi. Luôn bắt đầu từ head (bài mới nhất) và dừng lại khi chạm bài đã tồn tại (Tier 1 Early Stop qua `shouldStopPagination`).
    - `mode: "backfill"` (khi user yêu cầu cào lịch sử cũ): Mới sử dụng ACL để resume từ `lastCursor`.

---

#### Finding M2: Lỗ hổng thiếu `storeBatch` và `checkpointResolver` ở các Scraper VN
- **Lỗ hổng:**
  AD-3 quy định hook stream phát ra sau `storeBatch`.
  Tuy nhiên, mã nguồn XActions cho thấy:
  - `ShopeeCrawler` (`src/scrapers/ecom/shopee/crawler.js`) không hề gọi `this.store.storeBatch` (chỉ gọi `saveCheckpoint` trực tiếp).
  - Nhiều crawler VN như `chotot`, `topcv`, `masothue` không định nghĩa `checkpointResolver` trong descriptor.
- **Hai Unit minh họa:**
  - *Unit A (ShopeeCrawler):* Cào sản phẩm thành công, trả về `{ products, pageInfo }`. Do không gọi `storeBatch`, hook phát stream ở base class không bao giờ được kích hoạt.
  - *Unit B (Nowing Stream Consumer):* Ngồi chờ message của Shopee trên `stream:social:raw_posts` nhưng không bao giờ nhận được byte nào.
- **Hậu quả:** Toàn bộ dữ liệu cào từ Shopee và các crawler không gọi `storeBatch` bị kẹt, không thể đi vào data plane.
- **Đề xuất siết AD:**
  - Bổ sung vào **AD-3 Rule:** Chuẩn hóa luồng hoàn tất của crawler. Hook phát stream phải được đặt tại vòng đời kết thúc action của `AbstractCrawler.start()` (sau khi action handler trả về items), không phụ thuộc vào việc từng crawler con có tự giác gọi `storeBatch` hay không. Đồng thời bổ sung test case bắt buộc mọi crawler VN phải có `checkpointResolver`.

---

#### Finding M3: Xung đột Taxonomy giữa Platform Key của Nowing và Action Descriptor của XActions
- **Lỗ hổng:**
  AD-6 yêu cầu `UniversalScrapeTargetMapper` loại bỏ hard-code `PLATFORM_TOOL_MAP` và build dynamic map từ `x_actions_list` (AD-7).
  Trong cơ sở dữ liệu Nowing, trường `SocialMonitoredTarget.platform` lưu các định danh ghép (compound): `"chotot_category"`, `"shopee_keyword"`, `"topcv_search"`, `"masothue_lookup"`.
  Trong XActions, `x_actions_list` trả về các descriptor nguyên tử (atomic):
  `{ platform: "chotot", action: "posts", requiredArgs: ["category"] }`,
  `{ platform: "shopee", action: "search", requiredArgs: ["keyword"] }`.
- **Hai Unit minh họa:**
  - *Unit A (XActions x_actions_list):* Trả về danh sách platform chuẩn: `shopee`, `topcv`, `chotot`.
  - *Unit B (Nowing Dynamic Mapper):* Nhận target có `platform = "shopee_keyword"`. Mapper tìm trong danh sách descriptor không có platform nào tên là `"shopee_keyword"`. Mapper coi đây là platform không hỗ trợ (`unsupported`) và từ chối xử lý.
- **Hậu quả:** Toàn bộ các target hiện có trong hệ thống Nowing bị vô hiệu hóa khi chuyển sang dynamic discovery.
- **Đề xuất siết AD:**
  - Bổ sung vào **AD-6 Rule:** Định nghĩa quy tắc phân rã (decomposition pattern) chuẩn cho Nowing mapper:
    Chuỗi `<platform>_<target_type>` trong Nowing DB được phân rã thành: `platform = parts[0]`, `target_type = parts[1]`.
    Mapper đối chiếu `target_type` với danh sách `action` và `requiredArgs` trong descriptor của XActions để tự động suy ra tool call tương ứng.

---

#### Finding M4: Vi phạm phân tách tầng trách nhiệm trong Bảng ánh xạ lỗi (Error Policy Layering)
- **Lỗ hổng:**
  AD-10 quy định: *"1 bảng mapping trong adapter: `XACT_4291`→`retry(countdown=retry_after)`; `ACCOUNT_HIBERNATION`/`PROXY_EXHAUSTED`/`XACT_5030`→pause; `XACT_4010`→halt; `XACT_5000`→retry×3→DLQ ... Không rải if/else."*
  Tuy nhiên, `adapter_v2.py` là tầng giao tiếp I/O (Client/Adapter). Nó không sở hữu `task` instance của Celery, không sở hữu SQLAlchemy `session`, và không có thẩm quyền mutate trạng thái của model `SocialMonitoredTarget` (`_pause_target`, `_halt_target`).
  Nếu một thành phần khác (ví dụ FastAPI route cho user search live) gọi adapter, adapter không thể thực hiện các hành động Celery retry hay pause database model.
- **Hai Unit minh họa:**
  - *Unit A (Lập trình viên Adapter):* Implement bảng mapping trong adapter gọi thẳng `task.retry` hoặc `target.status = "paused"`. Khi adapter được gọi từ một script hoặc API controller không có Celery task context, code văng lỗi `NameError: name 'task' is not defined`.
  - *Unit B (Lập trình viên Celery Task):* Nhận exception chung chung từ adapter, không biết mã lỗi chi tiết là gì để thực hiện đúng hành vi Celery mong muốn.
- **Hậu quả:** Code bị coupled sai tầng kiến trúc, khó viết unit test và không tái sử dụng được adapter ở các bối cảnh khác ngoài Celery.
- **Đề xuất siết AD:**
  - Sửa đổi **AD-10 Rule:** Chia rõ 2 tầng mapping:
    1. **Tầng Adapter (Error Classification):** Ánh xạ error envelope `XACT_*` thành cây Exception domain chuẩn mực trong Python:
       `XActionsRateLimitError(retry_after)`, `XActionsResourceExhaustedError`, `XActionsAuthenticationError`, `XActionsFatalTargetError`.
    2. **Tầng Orchestrator (Task Policy):** Một bảng declarative policy dict đặt tại module Celery tasks mapping từ `Exception class` sang `TaskDirective(action="pause"|"retry"|"halt")`.

---

### LOW FINDINGS

#### Finding L1: Lệch Invariant về tính Idempotent giữa Spine và DB Schema thực tế
- **Lỗ hổng:**
  Spine (dòng 48 và 125) khẳng định: `UNIQUE(platform, external_post_id)` ở nowing DB.
  Nhưng schema thực tế tại `app/models/leads/social.py` (line 90) là:
  `UniqueConstraint("workspace_id", "platform", "external_post_id", name="uq_social_post")`.
- **Hậu quả:** Các thiết kế deduplication ở tầng trên dựa vào giả định bài viết là duy nhất toàn cầu (global unique) sẽ xung đột với thiết kế multi-tenant theo workspace của Nowing.
- **Đề xuất siết AD:** Cập nhật text của AD-SOC-6 trong Spine phản ánh chính xác schema: `UNIQUE(workspace_id, platform, external_post_id)`.

#### Finding L2: Độ lệch dung lượng cắt tỉa Redis Stream (MAXLEN 1M vs 20K)
- **Lỗ hổng:**
  AD-3 quy định trimming `MAXLEN ~1M`, trong khi code hiện tại của Nowing dùng `maxlen=20000`.
  Nếu 1 triệu thin events được lưu với payload lớn trên Redis mà không có RAM budget rõ ràng, Redis server có thể bị OOM trên môi trường production hạn chế tài nguyên.
- **Đề xuất siết AD:** Bổ sung vào AD-3 thông số cấu hình cụ thể: `REDIS_STREAM_MAXLEN` (mặc định 100,000 cho production, có thể override qua biến môi trường).

---

## Action Plan — Proposed AD Modifications

Để chuyển trạng thái Spine sang **ACCEPTED**, cần thực hiện các sửa đổi cụ thể sau vào `ARCHITECTURE-SPINE.md`:

1. **Sửa AD-2 (x_scrape Contract):**
   Quy định rõ tham số:
   `x_scrape({ platform, action, args: Record<string, any>, context?: { targetId?: string|number, workspaceId?: number }, accountId?, proxyUrl?, dryRun? })`.
   Kết quả trả về khi streaming bật là execution metadata, `data: []`.

2. **Sửa AD-3 (Stream Payload & Hook Location):**
   Di dời hook stream ra cuối pipeline `AbstractCrawler.start()`.
   Cố định schema payload snake_case đồng nhất:
   `{ id, platform, external_post_id, category, author_id, author_name, post_url, content_snippet, target_id, workspace_id, crawled_at, storage_ref, scraper_id }`.

3. **Sửa AD-5 (Loop-Aware Client Lifecycle):**
   Thay đổi từ "proc-scoped singleton" sang "loop-aware persistent client" có cơ chế tự bind lại khi Celery tạo Event Loop mới.

4. **Sửa AD-8 (Rate Limit & Multi-Tenant Protection):**
   Bổ sung quy định Nowing phải rate-limit outbound trước khi gọi MCP. Bổ sung header `X-Workspace-Id` vào XActions Governor để ngăn ngừa starvation giữa các workspace.

5. **Sửa AD-9 (Crawl Mode Distinction):**
   Tách rõ `mode: "delta"` (top-down crawl dừng tại duplicate, bỏ qua lastCursor) cho scheduled tasks và `mode: "backfill"` (tiếp tục từ lastCursor) cho historical tasks.

6. **Sửa AD-10 (Two-Tier Error Mapping):**
   Adapter chịu trách nhiệm parse mã `XACT_*` thành Typed Exceptions. Celery layer chịu trách nhiệm map Typed Exceptions thành hành vi task (`retry`, `pause`, `halt`).

