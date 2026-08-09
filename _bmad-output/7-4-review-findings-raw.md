# Raw Review Findings — Story 7.4

## Blind Hunter (bmad-review-adversarial-general)

### 1. Dead code trong thread.tsx - expandedConnectorGroups state
- **Severity:** P2
- **File:** `nowing_web/components/assistant-ui/thread.tsx` (lines 1111-1113, 1160-1170, 1338-1343)
- **Evidence:** `expandedConnectorGroups` state và `setConnectorGroupExpanded` callback được khai báo và sử dụng trong mobile drawer (Collapsible cho connector tool groups). Tuy nhiên, sau khi thay đổi composer menu thành `DropdownMenuSub` cho MCP Connectors, logic này không còn được sử dụng cho MCP submenu. State vẫn tồn tại nhưng chỉ được dùng cho connector tool groups trong drawer, không phải cho MCP Connectors như spec yêu cầu.
- **Why:** Code không rõ ràng về mục đích sử dụng của state này. Spec nói "mobile: single drill-in vaul drawer with submenus replacing in place", nhưng implementation hiện tại vẫn dùng Collapsible pattern cũ cho connector tool groups, không phải vaul drawer drill-in pattern.
- **Fix:** Xác định xem `expandedConnectorGroups` có còn cần thiết cho connector tool groups không. Nếu không, xóa dead code. Nếu cần, thêm comment rõ ràng về mục đích sử dụng.

### 2. openConnectorSubmenu state không được sử dụng
- **Severity:** P2
- **File:** `nowing_web/components/assistant-ui/thread.tsx` (line 1110, 1465)
- **Evidence:** `openConnectorSubmenu` state được khai báo nhưng chỉ được set khi menu đóng (line 1465). Không được sử dụng để control trạng thái mở/đóng của MCP Connectors submenu sau khi thay đổi thành `DropdownMenuSub`.
- **Why:** Dead code gây confusion. DropdownMenuSub tự quản lý state open/close, không cần manual state.
- **Fix:** Xóa `openConnectorSubmenu` state và `setOpenConnectorSubmenu` calls.

### 3. workspacePanelViewportClassName thiếu isConnectorsPage
- **Severity:** P1
- **File:** `nowing_web/components/layout/providers/LayoutDataProvider.tsx` (lines 722-732)
- **Evidence:** `isConnectorsActive` được thêm vào navItems (line 881, 886). Nhưng `workspacePanelViewportClassName` không bao gồm `isConnectorsPage` condition. Điều này có nghĩa là trang `/connectors` sẽ không có padding/viewport styling giống các trang workspace panel khác (Usage, Automations, Artifacts, Playgrounds, All Chats).
- **Why:** Inconsistent styling - trang connectors có thể trông khác biệt so với các trang khác trong workspace panel, gây UX inconsistency.
- **Fix:** Thêm condition cho isConnectorsPage vào workspacePanelViewportClassName.

### 4. client-layout.tsx - isConnectorsPage detection bằng string includes
- **Severity:** P2
- **File:** `nowing_web/app/dashboard/[workspace_id]/client-layout.tsx` (line 9)
- **Evidence:** `const isConnectorsPage = pathname?.includes("/connectors");`
- **Why:** String `includes` có thể false positive nếu có route khác chứa "/connectors" trong path (ví dụ: `/dashboard/123/some-connectors-related-page`). Nên dùng exact match hoặc regex pattern.
- **Fix:** Sử dụng exact match: `pathname?.endsWith("/connectors") || pathname?.includes("/connectors/")` hoặc dùng `usePathname()` và kiểm tra exact segment.

### 5. OverviewPane.tsx - groupsByType không được sử dụng
- **Severity:** P2
- **File:** `nowing_web/components/connectors/overview-pane.tsx` (lines 49-52)
- **Evidence:** `const groupsByType = useMemo(() => new Map(groups.map((g) => [g.connectorType, g])), [groups]);` Biến này được tạo nhưng không được sử dụng anywhere trong component.
- **Why:** Dead code, waste of computation. Có thể là leftover từ refactoring.
- **Fix:** Xóa `groupsByType` nếu không cần thiết, hoặc sử dụng nó thay vì lặp lại logic tìm group (line 71-73, 104-106).

### 6. LayoutDataProvider.tsx - syncChatTab effect bị quá mức
- **Severity:** P1
- **File:** `nowing_web/components/layout/providers/LayoutDataProvider.tsx` (lines 276-282)
- **Evidence:** `useEffect(() => { const chatId = currentChatId ?? null; syncChatTab({ chatId, workspaceId: Number(workspaceId) }); }, [currentChatId, workspaceId, syncChatTab]);` Diff này bỏ qua `title`, `chatUrl`, `visibility`, `hasComments` khi sync tab (trước đó có ở lines 857-869). Comment cũ nói "Avoid overwriting live SSE-updated tab titles with fallback values" nhưng mới lại bỏ qua title.
- **Why:** Tab titles có thể bị mất hoặc không sync đúng khi navigate. Việc bỏ qua các field này có thể là regression bug cho tab management.
- **Fix:** Kiểm tra xem việc bỏ qua các field này có intentional không. Nếu không, restore lại logic cũ hoặc thêm comment giải thích tại sao bỏ qua.

### 7. DocumentsSidebar.tsx - openDocumentTab thay đổi không có test
- **Severity:** P2
- **File:** `nowing_web/components/layout/ui/sidebar/DocumentsSidebar.tsx` (lines 28, 354, 1125)
- **Evidence:** Thay đổi từ `openEditorPanel` sang `openDocumentTab` khi preview document (line 1125). Đây là behavior change quan trọng - document mở trong tab thay vì editor panel. Không có test cho việc này trong diff.
- **Why:** Behavior change không được test có thể gây regression. User có thể gặp vấn đề khi mở document từ sidebar.
- **Fix:** Thêm test cho việc mở document từ sidebar, hoặc verify rằng test hiện tại đã cover behavior này.

### 8. OverviewPane.tsx - search không có debounce
- **Severity:** P2
- **File:** `nowing_web/components/connectors/overview-pane.tsx` (lines 54-57, 83-89)
- **Evidence:** Search input trực tiếp update state `searchQuery` onChange. `visibleDefinitions` được re-computed mỗi khi searchQuery thay đổi. Với nhiều connector definitions, điều này có thể gây performance issue.
- **Why:** Mỗi keystroke trigger re-filter của toàn bộ connector list. Với 50+ connectors, có thể gây lag trên device yếu.
- **Fix:** Thêm debounce cho search input (ví dụ 300ms) hoặc verify rằng CONNECTOR_DISPLAY_DEFINITIONS không quá lớn để cần debounce.

### 9. groupConnectorsByType.test.ts - test format không chuẩn
- **Severity:** P2
- **File:** `nowing_web/lib/connectors/group-connectors-by-type.test.ts`
- **Evidence:** Test file sử dụng plain Node.js `assert` và `console.log` thay vì vitest/jest framework. Không có `describe`/`it` blocks. Có thể không được chạy bởi CI test runner nếu chỉ chạy vitest.
- **Why:** Test có thể không được execute trong CI, giving false sense of coverage.
- **Fix:** Convert test sang vitest format với `describe`/`it` blocks và proper assertions.

### 10. ConnectorDetailPane.tsx - hook reuse comment misleading
- **Severity:** P2
- **File:** `nowing_web/components/connectors/connector-detail-pane.tsx` (lines 38-42)
- **Evidence:** Comment nói dialog được ẩn trên connectors page. Nhưng thực tế chỉ `ConnectorIndicator` được ẩn, không phải dialog component. `useConnectorDialog` hook vẫn có thể trigger dialog state nếu không được control properly.
- **Why:** Comment misleading có thể gây confusion cho future maintainers. Nếu dialog không được ẩn đúng cách, có thể gây bug.
- **Fix:** Clarify comment hoặc verify rằng dialog component thực sự được ẩn/disabled trên connectors page.

### 11. LayoutDataProvider.tsx - handleTabSwitch signature change không documented
- **Severity:** P2
- **File:** `nowing_web/components/layout/providers/LayoutDataProvider.tsx` (lines 931-949)
- **Evidence:** `handleTabSwitch` thay đổi từ nhận `Tab` sang `ResolvedTab` (line 933). Logic parse `entityId` từ `tab.entityId` thay vì `tab.chatId` (lines 935-936). Đây là breaking change trong contract nhưng không có comment giải thích.
- **Why:** Future maintainers có thể không hiểu tại sao signature thay đổi, gây confusion.
- **Fix:** Thêm comment giải thích tại sao thay đổi từ Tab sang ResolvedTab và logic parse mới.

### 12. isConnectorsPage không được defined trong LayoutDataProvider.tsx
- **Severity:** P1
- **File:** `nowing_web/components/layout/providers/LayoutDataProvider.tsx`
- **Evidence:** `isConnectorsActive` được defined (line 881) nhưng `isConnectorsPage` không được defined. Trong LayoutShell condition, `showTabs` logic sử dụng `isNewChatRoot` nhưng không có tương đương cho connectors page.
- **Why:** Inconsistent naming convention. `isConnectorsActive` dùng cho nav highlighting, nhưng không có `isConnectorsPage` cho layout logic. Có thể gây bug nếu cần layout-specific behavior cho connectors page.
- **Fix:** Thêm `isConnectorsPage` constant tương tự như `isNewChatRoot` (line 1002) và sử dụng nó trong layout logic nếu cần.

## Edge Case Hunter

### 1. hook.workspaceId có thể không khớp với workspaceId của trang trong ConnectorDetailPane
- **Edge case:** `useConnectorDialog` hook sử dụng `activeWorkspaceIdAtom` nhưng trang `/connectors` nhận `workspaceId` prop từ URL. Nếu active workspace khác với workspace trong URL, hook sẽ hoạt động với sai workspace.
- **File:** `nowing_web/components/connectors/connector-detail-pane.tsx:235`
- **Consequence:** Các thao tác connector (OAuth, indexing, edit) sẽ thực hiện trên sai workspace, gây lỗi hoặc data leak giữa workspace.
- **Fix:** Truyền workspaceId prop cho hook hoặc tạo wrapper hook chấp nhận workspaceId parameter, hoặc sử dụng prop workspaceId thay vì hook.workspaceId trong các child components.

### 2. YouTubeCrawlerView render khi hook.workspaceId là null/undefined
- **Edge case:** Line 273 kiểm tra `hook.workspaceId` nhưng không xử lý trường hợp null.
- **File:** `nowing_web/components/connectors/connector-detail-pane.tsx:273-276`
- **Consequence:** Nếu `hook.workspaceId` là null, YouTubeCrawlerView nhận null prop, có thể gây lỗi runtime khi component cố gắng sử dụng workspaceId.
- **Fix:** Thêm null check trong YouTubeCrawlerView hoặc đảm bảo hook không set isYouTubeView = true khi workspaceId null.

### 3. ConnectorEditView nhận workspaceId null khi hook.workspaceId undefined
- **Edge case:** Line 336 truyền `hook.workspaceId?.toString()` nhưng không có fallback.
- **File:** `nowing_web/components/connectors/connector-detail-pane.tsx:336`
- **Consequence:** ConnectorEditView nhận "undefined" string hoặc null, gây lỗi khi gọi API hoặc validate.
- **Fix:** Sử dụng prop workspaceId từ component cha thay vì hook.workspaceId, hoặc thêm fallback: `workspaceId={hook.workspaceId?.toString() || workspaceId}`.

### 4. Router.push trong thread.tsx không validate workspaceId
- **Edge case:** Chỉ kiểm tra `if (workspaceId)` không kiểm tra giá trị hợp lệ.
- **File:** `nowing_web/components/assistant-ui/thread.tsx:128, 176`
- **Consequence:** Nếu workspaceId là string không hợp lệ (ví dụ "abc"), router.push sẽ navigate đến URL không tồn tại, gây 404.
- **Fix:** Thêm validation: `if (workspaceId && !isNaN(Number(workspaceId)))` hoặc parse và kiểm tra trước khi push.

### 5. syncChatTab signature thay đổi nhưng không cập nhật tất cả callers
- **Edge case:** Diff thay đổi signature của syncChatTabAtom (chỉ nhận chatId và workspaceId) nhưng không kiểm tra xem có caller nào khác truyền title, chatUrl, visibility, hasComments không.
- **File:** `nowing_web/components/layout/providers/LayoutDataProvider.tsx:861-868`
- **Consequence:** Nếu có component khác gọi syncChatTab với các prop cũ, TypeScript sẽ báo lỗi runtime hoặc các prop bị bỏ qua gây mất data (title, visibility).
- **Fix:** Kiểm tra tất cả callers của syncChatTabAtom trong codebase và cập nhật, hoặc giữ backward compatibility trong atom implementation.

### 6. parseInt trong handleTabSwitch có thể trả về NaN
- **Edge case:** `Number.parseInt(tab.entityId, 10)` có thể trả về NaN nếu entityId không phải số hợp lệ.
- **File:** `nowing_web/components/layout/providers/LayoutDataProvider.tsx:936-941`
- **Consequence:** Nếu entityId là "abc" hoặc string không hợp lệ, parseInt trả về NaN, sau đó được filter out nhưng vẫn gây xử lý không cần thiết.
- **Fix:** Code đã có NaN check, nhưng nên thêm validation ở source (useResolvedTabs) để đảm bảo entityId luôn hợp lệ.

### 7. parseInt trong handleTabPrefetch có thể trả về NaN
- **Edge case:** Tương tự như trên, parseInt có thể trả về NaN.
- **File:** `nowing_web/components/layout/providers/LayoutDataProvider.tsx:956-960`
- **Consequence:** Code đã có NaN check, nhưng nếu entityId là số âm hoặc 0, prefetch sẽ không chạy (có thể là intended behavior).
- **Fix:** Đã xử lý đúng với NaN check và > 0 check.

### 8. parseInt trong handleDelete fallback tab có thể trả về NaN
- **Edge case:** Tương tự, parseInt có thể trả về NaN.
- **File:** `nowing_web/components/layout/providers/LayoutDataProvider.tsx:981-990`
- **Consequence:** Đã có NaN check, nên tương đối an toàn.
- **Fix:** N/A - đã được xử lý.

### 9. useZeroDocumentTypeCounts trong OverviewPane không có error handling
- **Edge case:** Hook có thể throw error hoặc return undefined nếu workspaceId không hợp lệ hoặc API fail.
- **File:** `nowing_web/components/connectors/overview-pane.tsx:705`
- **Consequence:** Nếu documentTypeCounts là null/undefined, getDocumentCountForConnector có thể throw error.
- **Fix:** Thêm null check: `const documentCount = definition.connectorType && documentTypeCounts ? getDocumentCountForConnector(...) : undefined`.

### 10. localeCompare trong groupConnectorsByType có thể throw trên non-string
- **Edge case:** Nếu getConnectorTypeDisplay trả về non-string (null, undefined, number), localeCompare sẽ throw.
- **File:** `nowing_web/lib/connectors/group-connectors-by-type.ts:1465`
- **Consequence:** Nếu title không phải string, sort sẽ throw TypeError, làm hỏng connector rail và overview pane.
- **Fix:** Thêm fallback: `.sort((a, b) => String(a.title || "").localeCompare(String(b.title || "")))`.

### 11. isCloudLoading logic sử dụng "unknown" type có thể không đủ
- **Edge case:** Zero query result type "unknown" có thể không phải trạng thái loading duy nhất.
- **File:** `nowing_web/components/layout/ui/sidebar/DocumentsSidebar.tsx:1210-1211`
- **Consequence:** Nếu Zero query có loading state khác (ví dụ "loading", "pending"), spinner sẽ không hiển thị khi đang load.
- **Fix:** Kiểm tra tất cả loading states của Zero query hoặc sử dụng isLoading flag từ query result.

### 12. Deletion check không thể thực hiện
- **Edge case:** File `references/deletion-check.md` không tồn tại trong repository.
- **File:** N/A
- **Consequence:** Không thể kiểm tra xem việc xóa code có gây regression không (ví dụ: xóa CloudDocumentsSkeleton, xóa cloud connector items từ Import menu).
- **Fix:** Tạo file deletion-check.md theo template hoặc bỏ qua deletion check nếu không cần thiết cho story này.

### 13. groupConnectorsByType với displayTypes undefined
- **Edge case:** OverviewPane truyền `displayTypes: undefined` nhưng function không xử lý undefined một cách rõ ràng.
- **File:** `nowing_web/components/connectors/overview-pane.tsx:713`
- **Consequence:** Function sẽ bỏ qua displayTypes loop (line 1443-1449), chỉ hiển thị connectors đã connect. Đây có thể là intended behavior cho overview pane, nhưng nên rõ ràng hơn.
- **Fix:** N/A - có vẻ là intended behavior để overview pane chỉ hiển thị connected connectors trong rail.

### 14. connectors null/undefined trong thread.tsx MCP submenu
- **Edge case:** `(connectors ?? [])` cast nhưng không validate từng item.
- **File:** `nowing_web/components/assistant-ui/thread.tsx:107, 155`
- **Consequence:** Nếu connectors array chứa item không hợp lệ (missing connector_type), groupConnectorsByType có thể throw hoặc tạo group với connectorType undefined.
- **Fix:** Thêm validation trong groupConnectorsByType để skip items không có connector_type hợp lệ.

## Acceptance Auditor

### 1. AC5 - Composer add-menu: Mobile pattern không được triển khai
- **AC/constraint:** "Given the composer '+' menu, When on mobile, Then a single drill-in vaul drawer with submenus replacing in place and a back button."
- **Evidence:** Diff chỉ hiển thị thay đổi cho desktop `DropdownMenuSub` (lines 100-136, 148-184 trong thread.tsx). Không có bất kỳ thay đổi nào liên quan đến drawer/vaul pattern cho mobile. Không có `isMobile` check hoặc logic phân biệt desktop/mobile.
- **Severity:** P1
- **Fix:** Thêm logic phân biệt desktop/mobile trong composer add-menu. Mobile nên sử dụng drawer component (spec đề xuất `components/ui/drawer.tsx` đã tồn tại) với drill-in pattern và back button thay vì `DropdownMenuSub`.

### 2. Task - LiveConnectorConnectedCard fallback không được triển khai
- **Spec constraint:** "Add `LiveConnectorConnectedCard`-equivalent fallback manage view for live non-MCP connectors (native/Composio Gmail & Calendar) in the detail pane."
- **Evidence:** Diff không chứa bất kỳ tham chiếu nào đến `LiveConnectorConnectedCard`. `ConnectorDetailPane` (lines 193-434) chỉ sử dụng `useConnectorDialog` hook để render các view tiêu chuẩn (connect/edit/accounts) mà không có fallback đặc biệt cho live non-MCP connectors.
- **Severity:** P2
- **Fix:** Xác định xem `LiveConnectorConnectedCard` có thực sự cần thiết cho Nowing hay không. Nếu cần, thêm component này vào `ConnectorDetailPane` như fallback cho các live connectors (Gmail, Calendar) khi chúng không phải MCP. Nếu không cần, cập nhật spec để loại bỏ yêu cầu này.

### 3. Task - MCP icon `mask: currentColor` không được xác minh/thay đổi
- **Spec constraint:** "Verify/adjust MCP icon so it uses `mask: currentColor` (check `nowing_web/components/icons/providers/`)."
- **Evidence:** Diff không có bất kỳ thay đổi nào đối với file icon. File hiện tại `/public/connectors/modelcontextprotocol.svg` sử dụng `fill="#000"` (hardcoded black) thay vì `mask: currentColor`. Các icon khác như Slack, Notion cũng sử dụng `fill` với màu sắc cụ thể, không phải `mask: currentColor`.
- **Severity:** P2
- **Fix:** Nếu upstream SurfSense thực sự yêu cầu `mask: currentColor` cho MCP icon, hãy convert SVG hiện tại để sử dụng mask thay vì fill. Nếu không, hãy cập nhật spec để phản ánh thực tế rằng icon sử dụng fill.

### 4. Task - messages/en.json không được cập nhật
- **Spec constraint:** "Update UX copy to 'Integrations' where the connector concept is labeled (docs/UI strings; verify `messages/en.json` keys if copy lives there)."
- **Evidence:** Diff không có thay đổi nào đối với `messages/en.json`. Mặc dù copy trong components đã được cập nhật sang "Integrations" (page title, sidebar nav, search placeholder, rail header), nhưng spec yêu cầu kiểm tra và cập nhật `messages/en.json` nếu copy sống ở đó.
- **Severity:** P2
- **Fix:** Kiểm tra `messages/en.json` để xem có bất kỳ key nào liên quan đến connectors cần cập nhật sang "Integrations" không.

### 5. Tests - Component/integration test cho rail health states không được triển khai
- **Spec task:** "Component/integration test for the rail health states (syncing vs failed vs connected) using mocked `connectorsAtom` data."
- **Evidence:** Diff chỉ chứa test cho `groupConnectorsByType` (lines 1308-1396). Không có test nào cho `ConnectorRail` hoặc health states.
- **Severity:** P2
- **Fix:** Thêm component test cho `ConnectorRail` để verify syncing/failed/connected states.

### 6. Tests - Navigation test không được triển khai
- **Spec task:** "Navigation test: `/dashboard/{workspace_id}/connectors` renders page + rail + overview; tapping a connector switches detail pane by account-count routing."
- **Evidence:** Không có test navigation nào trong diff.
- **Severity:** P2
- **Fix:** Thêm navigation/integration test.
