# Báo Cáo Nghiên Cứu Kỹ Thuật: Đánh Giá Nâng Cấp CdpBridge Hỗ Trợ Đa Tab (Multi-Tab CDP Session Architecture)

**Mã tài liệu:** `RESEARCH-EPIC-32-CDP-MULTITAB`  
**Thuộc Epic:** Epic 32 (Browser Operator Runtime, Interactive Takeover & CDP Lifecycle) / Action Item 33  
**Tác giả:** Core Browser & Backend Engineering Team  
**Ngày lập:** 2026-10-13  
**Trạng thái đề xuất:** `DEFER` (Khuyến nghị tạm hoãn triển khai code, sẵn sàng kích hoạt khi đủ điều kiện)  

---

## 1. Tóm Tắt Điều Hành (Executive Summary)

Trong khuôn khổ hoàn thiện Epic 32, runtime điều khiển trình duyệt của Nowing Extension (`CdpBridge` tại `nowing_browser_extension/background/cdp-bridge.ts`) đã được gia cố toàn diện về:
- Cơ chế fail-fast khi debugger bị ngắt kết nối (`chrome.debugger.onDetach`).
- Bảo đảm kết quả duy nhất (Single Result Guarantee) chống ô nhiễm hàng đợi Redis.
- Xác thực mật mã token phiên (`session_token`) và nhật ký kiểm toán hành vi (audit trail).

Tuy nhiên, toàn bộ luồng điều khiển của `CdpBridge` hiện đang phụ thuộc vào biến trạng thái đơn lẻ `activeDebuggeeTabId: number | null` và hàng đợi lệnh tuần tự toàn cục (`queued: CdpCommand[]`). Thiết kế này giới hạn extension chỉ có thể tương tác với **duy nhất 1 tab tại một thời điểm**.

Báo cáo nghiên cứu này phân tích chi tiết:
1. Thực trạng kiến trúc đơn tab và các giả định ngầm trong `cdp-bridge.ts`.
2. Bản thiết kế kỹ thuật chuyển đổi sang mô hình `Map<number, SessionContext>` để quản lý đa tab độc lập.
3. Phân tích phạm vi tác động (blast radius) xuyên suốt extension, UI takeover và backend.
4. Ma trận quyết định: lý do khuyến nghị **hoãn (defer)** và bộ tiêu chí kích hoạt triển khai thực tế.

---

## 2. Phân Tích Kiến Trúc Hiện Tại Của `cdp-bridge.ts` (Current Single-Tab Architecture)

Hiện tại, file `nowing_browser_extension/background/cdp-bridge.ts` (855 dòng code) được thiết kế xoay quanh mô hình xử lý đơn nhiệm (single-tenant / single-tab runner):

```text
SSE Stream (/dsh/cdp/stream)
            │
            ▼
    _enqueueCommand() ───► processing = true (Global Lock)
            │
            ▼
     handleCdpCommand()
      ├── _attachDebugger(tabId) ──► chrome.debugger.attach({ tabId })
      ├── Execute Action (click, fill, navigate, extract, screenshot...)
      └── detachDebugger() (Finally block) ──► chrome.debugger.detach({ tabId })
```

### 2.1. Các Giả Định Đơn Tab Cứng (Hardcoded Single-Tab Assumptions)

1. **Trạng thái debuggee duy nhất:**
   ```typescript
   private activeDebuggeeTabId: number | null = null;
   private intentionalDetachTabIds = new Set<number>();
   private currentCommand: { cmd: CdpCommand; alreadyHandled: boolean } | null = null;
   private activeSessionToken: string | null = null;
   private processing = false;
   private queued: CdpCommand[] = [];
   ```
   - Chỉ có một biến `activeDebuggeeTabId`. Nếu một lệnh mới yêu cầu tab khác, lệnh đó sẽ phải chờ hoặc ngắt kết nối của tab hiện tại.
   - `processing: boolean` tạo thành một khóa toàn cục (global mutex). Mọi lệnh đến từ SSE stream đều bị ép vào một hàng đợi đơn `queued` với kích thước giới hạn `maxQueueSize = 20`.

2. **Cơ chế Attach/Detach sau mỗi câu lệnh (Per-Command Churn):**
   Trong `handleCdpCommand`:
   ```typescript
   try {
       await this._attachDebugger(tabId);
       // ... thực thi action ...
   } finally {
       await this.detachDebugger();
   }
   ```
   - Extension gắn (`attach`) và gỡ (`detach`) debugger liên tục cho mỗi thao tác (navigate, click, extract, screenshot).
   - Thiết kế này nhằm đảm bảo thanh cảnh báo infobar của Chrome ("*Nowing is debugging this browser*") không hiển thị vĩnh viễn gây phiền người dùng, đồng thời tránh rò rỉ bộ nhớ. Tuy nhiên, việc attach/detach liên tục tạo ra độ trễ 100–300ms cho mỗi lệnh và khiến việc quản lý nhiều tab cùng lúc trở nên bất khả thi nếu không có bộ đếm phiên (ref count/session context).

3. **Cơ chế xử lý Detach bất ngờ (`_handleOnDetach`):**
   ```typescript
   if (this.activeDebuggeeTabId === null || tabId !== this.activeDebuggeeTabId) {
       return;
   }
   this.activeDebuggeeTabId = null;
   const droppedCommands = this.queued;
   this.queued = [];
   ```
   - Khi nhận sự kiện `onDetach` từ một tab, `CdpBridge` xóa sạch toàn bộ hàng đợi `this.queued = []` và gửi thông báo lỗi `DEBUGGER_DETACHED` cho tất cả các lệnh đang xếp hàng.
   - Trong môi trường đa tab, nếu Tab A bị đóng, hành vi này sẽ vô tình huỷ toàn bộ các lệnh của Tab B và Tab C đang chờ xử lý.

4. **Tìm kiếm Tab đích (`_findMatchingTab`):**
   - Hàm `_findMatchingTab` duyệt qua `allTabs = await chrome.tabs.query({})` và tìm tab khớp hostname hoặc lấy tab đang active (`allTabs.find(t => t.active)`). Nếu không tìm thấy, nó tạo tab mới với `active: true`.
   - Nếu chạy ngầm nhiều crawler cùng lúc, việc mở tab với `active: true` liên tục sẽ cướp tiêu điểm (focus stealing), gián đoạn thao tác của người dùng trên máy tính.

5. **Trạng thái Human Takeover trong UI (`popup.tsx`):**
   - Khi phát hiện CAPTCHA hoặc OTP challenge:
     ```typescript
     await storage.set("activeMissionId", mission_id);
     ```
   - Popup extension (`popup.tsx:18`) chỉ đọc một biến đơn lẻ `activeMissionId`. Nếu 2 tab gặp challenge cùng lúc, mission id thứ hai sẽ ghi đè mission id thứ nhất, làm mất khả năng giải cứu mission trước đó.

6. **Các listener vòng đời tab tại `background/index.ts`:**
   ```typescript
   chrome.tabs.onRemoved.addListener(async (tabId) => {
       const bridge = CdpBridge.getInstance();
       if (bridge.getActiveDebuggeeTabId() === tabId) {
           await bridge.detachActiveDebugger();
       }
   });
   ```
   - Các sự kiện `onReplaced` và `onRemoved` chỉ so khớp với một tab ID duy nhất trả về từ `getActiveDebuggeeTabId()`.

---

## 3. Đề Xuất Thiết Kế Kiến Trúc Mới: `Map<number, SessionContext>`

Để mở rộng hỗ trợ nhiều tab đồng thời mà không phá vỡ các bảo đảm an toàn đã xây dựng trong Epic 32, đề xuất chuyển đổi sang mô hình quản lý phiên phân tán theo từng Tab ID:

```text
               SSE Stream (/dsh/cdp/stream)
                            │
                            ▼
                Session Router / Dispatcher
             (Phân phối theo cmd.mission_id)
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
   SessionContext     SessionContext     SessionContext
     (Tab ID: 101)      (Tab ID: 102)      (Tab ID: 103)
   ├── Mission A      ├── Mission B      ├── Mission C
   ├── Local Queue    ├── Local Queue    ├── Local Queue
   └── State: RUN     └── State: WAIT    └── State: TAKEOVER
```

### 3.1. Cấu Trúc Dữ Liệu `SessionContext`

```typescript
export type SessionState = 
    | "initializing" 
    | "attached" 
    | "executing" 
    | "awaiting_human" 
    | "detaching" 
    | "terminated";

export interface SessionContext {
    /** Tab ID tương ứng trong Chrome */
    tabId: number;
    /** Mission ID của tác vụ DSH đang sở hữu tab này */
    missionId: string;
    /** User ID sở hữu tác vụ */
    userId: string;
    /** Token xác thực phiên do backend cấp phát */
    sessionToken: string | null;
    /** Thời điểm khởi tạo phiên (epoch ms) */
    createdAt: number;
    /** Thời điểm nhận lệnh gần nhất để phát hiện zombie tab */
    lastActivityAt: number;
    /** Trạng thái hiện tại của phiên */
    state: SessionState;
    /** Lệnh đang được thực thi trên tab */
    currentCommand: {
        cmd: CdpCommand;
        alreadyHandled: boolean;
    } | null;
    /** Hàng đợi lệnh cục bộ riêng của tab này */
    queue: CdpCommand[];
    /** Cờ đánh dấu chủ động detach (tránh kích hoạt onDetach handler) */
    isIntentionalDetach: boolean;
}
```

### 3.2. Quản Lý Phiên (Session Registry) Trong `CdpBridge`

Thay thế các thuộc tính đơn lẻ bằng hai bản đồ tra cứu (O(1)):
```typescript
class CdpBridge {
    // Tra cứu phiên theo Tab ID (dùng cho Chrome debugger events)
    private sessions = new Map<number, SessionContext>();
    
    // Tra cứu Tab ID theo Mission ID (dùng khi dispatch lệnh từ SSE)
    private missionToTab = new Map<string, number>();

    // Giới hạn số lượng tab debug tối đa chạy cùng lúc để bảo vệ tài nguyên
    private readonly MAX_CONCURRENT_SESSIONS = 3;
}
```

### 3.3. Mô Hình Đồng Thời (Concurrency Model)

1. **Tuần tự hoá theo từng Tab (Per-Tab FIFO Serialization):**
   - Các lệnh thuộc cùng một `mission_id` (ví dụ: navigate -> click -> fill -> extract) phải thực thi tuần tự tuyệt đối. Mỗi `SessionContext` sở hữu một `queue` riêng và một vòng lặp `_processNextSessionCommand(session)`.
2. **Song song hoá xuyên Tab (Cross-Tab Concurrency):**
   - Lệnh của Tab 101 và Tab 102 thực thi hoàn toàn độc lập, không block lẫn nhau.
   - Khi lệnh của Tab 101 đang chờ DOM render (`Page.loadEventFired`), Tab 102 vẫn có thể tiếp tục thực thi click/scroll.
3. **Bộ điều phối tài nguyên (Bounded Concurrency Semaphore):**
   - Giới hạn cứng tối đa `MAX_CONCURRENT_SESSIONS = 3` (hoặc 5 trên máy cấu hình mạnh).
   - Nếu nhận được lệnh cho một `mission_id` mới khi số session đã đạt ngưỡng tối đa, lệnh mới sẽ bị từ chối với mã lỗi `WORKER_BUSY_MAX_CONCURRENCY` hoặc xếp vào hàng đợi chờ session rảnh rỗi.

### 3.4. Vòng Đời Sự Kiện (Lifecycle Events Handling)

| Sự kiện | Hành vi trong mô hình Multi-Tab |
|---|---|
| **Lệnh mới từ SSE** | Kiểm tra `missionToTab.get(cmd.mission_id)`. Nếu đã có session, đẩy vào `session.queue`. Nếu chưa có, khởi tạo `SessionContext`, gắn `tabId` và bắt đầu xử lý. |
| **`chrome.debugger.onDetach`** | Nhận `source.tabId`. Lấy `session = sessions.get(tabId)`. Chỉ xóa bỏ `session.queue` và gửi `DEBUGGER_DETACHED` cho riêng `session.missionId`. **Tuyệt đối không ảnh hưởng tới các session khác.** Sau đó xóa `tabId` khỏi `sessions` và `missionToTab`. |
| **`chrome.tabs.onRemoved`** | Nếu `sessions.has(tabId)`: đánh dấu session bị đóng đột ngột, dọn dẹp debugger target, gửi kết quả thất bại `TAB_CLOSED_BY_USER` về backend và xóa session. |
| **Phát hiện CAPTCHA (`detect_challenge`)** | Chuyển trạng thái `session.state = "awaiting_human"`. Lưu thông tin vào danh sách các mission cần can thiệp: `activeTakeovers.set(mission_id, { tabId, challenge })`. |
| **Kết thúc Mission (`finish` / `abort`)** | Chủ động gỡ debugger (`chrome.debugger.detach({ tabId })`), đóng tab ngầm nếu tab đó do crawler tự sinh, và giải phóng bộ nhớ session. |

---

## 4. Phân Tích Phạm Vi Tác Động (Blast Radius Analysis)

| Thành phần | Mức độ tác động | Chi tiết thay đổi cần thực hiện |
|---|---|---|
| **`background/cdp-bridge.ts`** | **Rất cao (Major Rewrite)** | Thay thế toàn bộ quản lý state đơn lẻ bằng `Map<number, SessionContext>`. Tách riêng hàng đợi lệnh cho từng tab. Cập nhật các helper method `_sendCommand`, `_waitForEvent`, `_handleOnDetach`, `_captureCappedScreenshot` để nhận `SessionContext` thay vì đọc state toàn cục. |
| **`background/index.ts`** | **Trung bình** | Cập nhật các listener `chrome.tabs.onRemoved`, `chrome.tabs.onReplaced` để kiểm tra `bridge.hasSession(tabId)` và gọi `bridge.terminateSession(tabId)` thay vì hàm đơn `getActiveDebuggeeTabId()`. |
| **Popup UI (`popup.tsx`)** | **Cao** | Thiết kế lại giao diện Takeover. Thay vì hiển thị một thông báo đơn lẻ cho `activeMissionId`, popup cần render danh sách các mission đang chờ (`activeTakeovers: MissionTakeoverItem[]`). Người dùng có thể chọn chuyển tab tương ứng để giải CAPTCHA và bấm nút Resume cho từng nhiệm vụ riêng biệt. |
| **Backend SSE Stream (`cdp.py` / `cdp_stream`)** | **Thấp** | Payload lệnh CDP hiện tại đã có sẵn `mission_id` và `command_id`. SSE stream không cần đổi schema, nhưng worker dispatcher ở backend cần điều phối phân bổ nhiệm vụ có tính toán concurrency limit của từng client. |
| **Backend Celery Worker (`dsh_worker_browser_operator.py`)** | **Thấp** | Celery worker hiện tại khóa và chờ kết quả trên kênh Redis riêng biệt theo từng `command_id` và `mission_id`. Backend vốn đã được thiết kế phân tán theo từng nhiệm vụ, nên không chịu ảnh hưởng trực tiếp từ việc extension chạy đa tab. |
| **Hệ thống Test (Unit & E2E)** | **Cao** | Cần cập nhật bộ mock trong các unit test của browser extension; bổ sung kịch bản test Playwright MV3 kiểm thử việc mở đồng thời 2 tab debuggee và kiểm tra tính cách ly (isolation) khi 1 tab bị detach. |

---

## 5. Ma Trận Đánh Giá & Khuyến Nghị (Decision & Recommendation)

### 5.1. Khuyến Nghị Chính Thức: **DEFER (TẠM HOÃN TRIỂN KHAI)**

Đội ngũ kỹ thuật khuyến nghị **CHƯA TRIỂN KHAI** tính năng Multi-Tab `CdpBridge` trong giai đoạn hiện tại (Sprint này), vì các lý do sau:

1. **Tính Ổn Định Đang Ở Mức Cao Nhất:**  
   Kiến trúc đơn tab hiện tại sau các bản vá của Epic 32 đã đạt độ tin cậy tuyệt đối (0% zombie mission, fail-fast <57ms khi detach, single result guarantee hoàn hảo). Việc cấu trúc lại toàn bộ core bridge sang đa tab tiềm ẩn nguy cơ phá vỡ tính ổn định đang có.
2. **Hạn Chế Tài Nguyên Của Trình Duyệt Client:**  
   Việc chạy 3–5 phiên Chrome DevTools Protocol song song trên máy tính cá nhân của người dùng (khi extension được cài đặt trên máy thật của khách hàng) sẽ tiêu tốn đáng kể CPU, RAM và có thể gây đơ lag trình duyệt chính của họ.
3. **Nguy Cơ Bị Phát Hiện Bot (Anti-Bot Fingerprinting):**  
   Nhiều tab cào dữ liệu hoạt động song song từ cùng một địa chỉ IP và cùng một instance trình duyệt sẽ kích hoạt ngay lập tức cơ chế phòng vệ của Cloudflare, Akamai và DataDome. Việc chạy tuần tự từng tác vụ với khoảng dừng tự nhiên (jitter delay) hiện mang lại tỷ lệ trích xuất thành công cao hơn nhiều.
4. **Yêu Cầu Nghiệp Vụ Hiện Tại Chưa Cần Thiết:**  
   Tất cả các luồng DSH hiện hành (tìm kiếm lead, xác minh số điện thoại, làm giàu dữ liệu BĐS/việc làm) đều hoạt động theo mô hình tuần tự theo đợt (batch pipeline). Chưa có nghiệp vụ nào yêu cầu một client đơn lẻ phải scrape 5 trang web cùng một giây.

### 5.2. Các Điều Kiện Kích Hoạt Triển Khai (Trigger Conditions)

Tính năng Multi-Tab CdpBridge sẽ được kích hoạt chuyển sang trạng thái `In-Progress` khi và chỉ khi thỏa mãn **ít nhất 1 trong 3 điều kiện** sau:

- [ ] **Trigger 1 (Throughput Bottleneck):** Hàng đợi nhiệm vụ DSH của hệ thống vượt ngưỡng backlog > 100 missions/giờ trên mỗi worker pool, và thời gian chờ đợi trở thành rào cản SLA của khách hàng trả phí.
- [ ] **Trigger 2 (Multi-Target Research Crawl Feature):** Xuất hiện user story yêu cầu tính năng nghiên cứu sâu đa nguồn (Deep Research / Pulse Crawl) cần tải và đối chiếu đồng thời nội dung từ 3–5 website song song trong cùng một truy vấn của người dùng.
- [ ] **Trigger 3 (Headless Worker Dedicated Infrastructure):** Nowing triển khai cụm browser runner chuyên dụng chạy trên hạ tầng Dokploy/Docker (ví dụ cụm Chromium headless chuyên biệt) thay vì phụ thuộc hoàn toàn vào extension cài trên máy desktop của người dùng.

---

## 6. Ước Lượng Nỗ Lực Triển Khai (Effort Estimation)

Khi các điều kiện kích hoạt được thỏa mãn, kế hoạch triển khai sẽ được chia thành 4 giai đoạn cụ thể:

| Giai đoạn | Nội dung công việc | Nỗ lực ước lượng |
|---|---|---|
| **Phase 1** | Tái cấu trúc Core `CdpBridge`: chuyển sang `Map<number, SessionContext>`, xây dựng bộ điều phối hàng đợi per-tab và bounded concurrency semaphore (3 tabs max). | **2.5 ngày công** |
| **Phase 2** | Nâng cấp Takeover UI trên `popup.tsx`: hỗ trợ hiển thị danh sách đa mission, lựa chọn tab cần can thiệp thủ công, và cơ chế chuyển đổi tiêu điểm mượt mà. | **1.5 ngày công** |
| **Phase 3** | Gia cố vòng đời Tab & Giám sát rò rỉ bộ nhớ: xử lý các case `tabs.onRemoved`, `tabs.onReplaced`, `windows.onFocusChanged`, và cơ chế tự động dọn dẹp zombie sessions (TTL 10 phút). | **1.0 ngày công** |
| **Phase 4** | Xây dựng Test Suite & E2E Automation: unit tests cho multi-tab router, tích hợp Playwright MV3 fixture kiểm thử kịch bản 2 tab chạy song song và 1 tab detach. | **1.5 ngày công** |
| **Tổng cộng** | | **6.5 ngày công (~1.3 tuần làm việc)** |

---

## 7. Kết Luận

Nghiên cứu khẳng định việc nâng cấp `CdpBridge` sang kiến trúc `Map<number, SessionContext>` là hoàn toàn khả thi về mặt kỹ thuật và đã có bản thiết kế kiến trúc hoàn chỉnh. Tuy nhiên, quyết định tối ưu nhất ở thời điểm hiện tại là **giữ nguyên kiến trúc đơn tab ổn định của Epic 32 và lưu trữ báo cáo này làm tài liệu nền tảng khi mở rộng sang Epic 36+**.
