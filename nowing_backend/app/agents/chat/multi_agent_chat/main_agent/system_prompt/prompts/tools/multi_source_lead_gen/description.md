- `multi_source_lead_gen` — Search multiple Vietnamese lead sources at once
  (Batdongsan, Chợ Tốt, Mua Bán, TopCV, ITviec, VietnamWorks, Masothue, Mua Sắm Công) and
  persist the results to the workspace lead table.
  - **For any request about Vietnamese prospects, leads, candidates, companies,
    properties, or real-estate listings, this is the FIRST and ONLY tool to call
    in the first turn.** Do NOT start a `write_todos` plan and do NOT dispatch
    parallel `task` calls to `batdongsan`, `chotot`, `chotot_bds`, `muaban_bds`,
    `topcv`, `itviec`, `vn_jobs`, `vietnamworks`, `masothue`, or `muasamcong` directly for the same query.
  - This single tool already runs the relevant sources concurrently, deduplicates,
    filters DNC, encrypts PII, and persists to the lead table.
  - Only fall back to a single-source `task` if the user explicitly asks for a
    specific source that this tool did not cover, or after this tool has
    returned an error.
  - Args:
    - `query` (string, required): a concrete Vietnamese/English description
      of the target leads (e.g., "20 nhà đất Hà Nội giá dưới 5 tỷ",
      "công ty AI Agent tuyển dụng tại TP.HCM").
    - `table_id` (string, optional): a lead table id if the user already has
      a table open or named. Omit when no specific table was mentioned.
    - `locations` (list of strings, optional): city/province names to scope
      the search (e.g., `["Hà Nội"]` or `["TP.HCM", "Đà Nẵng"]`).
  - Returns: a markdown table with discovered leads plus a persistence summary.
    The tool auto-detects user intent:
    - Buyer/search intent ("tìm nhà", "cần mua") returns seller listings.
    - Seller/listing intent ("tôi cần bán", "ký gửi") returns comparable
      listings framed as "tin đăng bán tương tự / đối thủ cạnh tranh" with
      1-click follow-up actions (Tìm người mua, Lấy SĐT chủ tin, Phân tích giá).
    Present the table to the user and offer next steps (e.g., unlock phone,
    draft outreach, or save to a specific workspace table).
