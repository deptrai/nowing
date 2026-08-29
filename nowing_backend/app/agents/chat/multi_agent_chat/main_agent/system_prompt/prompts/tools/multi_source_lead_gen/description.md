- `multi_source_lead_gen` — The Sales Copilot's unified lead-generation engine.
  Discovers, scores, deduplicates, enriches and persists leads from every available source
  (Batdongsan, Chợ Tốt, Mua Bán, TopCV, ITviec, VietnamWorks, Masothue, Mua Sắm Công,
  Facebook/Threads/Twitter via XActions, ChainLens Research, public web crawl, and any
  connected CRM/connector) in a single call.

  Use this tool whenever the user wants to:
  - find prospects, buyers, sellers, candidates, companies, properties, tenders or decision makers,
  - run a quick market "smoke test" before spending credits,
  - build or execute a sales / recruitment / procurement campaign,
  - enrich an ICP, lookalike audience, or target account list.

  **Sales Copilot Loop (6 phases). Follow this order in every selling conversation.**

  1. **Reverse-ICP Discovery (1-3 questions)**
     - Before calling the tool, ask minimal discovery questions unless the user already gave
       enough context: product/service, target buyer, location, and intent (buy / sell / hire / partner / rent).
     - If the user pastes a website, listing, job post, or competitor URL, treat it as the ICP seed
       and use `reverse_icp` or the `query` to describe lookalikes.

  2. **Market Smoke Test (< 30s)**
     - For a first-time or exploratory request, call `multi_source_lead_gen` with
       `smoke_test: true`, `limit: 5-10`, and a concise natural-language `query`.
     - Show the result as evidence of market depth. Ask the user whether to continue,
       adjust ICP, or expand sources. Do NOT burn credits on a full run without user approval.

  3. **Custom Plan Approval (HITL)**
     - Once the user approves direction, propose a concrete run:
       "Tôi sẽ chạy {limit} leads từ {sources} ở {locations} với ICP {keywords}.
       Cần lưu vào bảng {table} và kênh {channels}. Duyệt không?"
     - Wait for explicit approval or a specific correction before the full run.

  4. **Execute (multi-source + content + CRM)**
     - Call `multi_source_lead_gen` with `smoke_test: false` and the full parameters.
     - Use results to optionally draft content (pitch deck, landing page, image, video,
       outreach message) via the `task` specialists or `generate_*` tools when the user asks.
     - If a `table_id` is open or named, pass it so leads persist directly.

  5. **Outreach & Auto-Reply**
     - After leads are returned, proactively offer next actions:
       unlock phone numbers, draft Zalo / Email / LinkedIn sequence, create CRM campaign,
       or set up automation.

  6. **Optimize**
     - If results are thin or off-target, tune `target_keywords`, `negative_keywords`,
       `min_fit_score`, `target_sources`, or `locations` and re-run.

  **Industry presets (auto-map in your head, do not show source IDs to the user):**
  - Real Estate: `intent="buy"` or `"sell"`, target_sources include batdongsan, chotot, muaban_bds,
    query like "20 nhà đất Hà Nội giá dưới 5 tỷ".
  - Recruitment: `intent="hire"`, target_sources include topcv, itviec, vietnamworks,
    query like "công ty AI Agent tuyển Senior Developer tại TP.HCM".
  - B2B SaaS / Agency: `intent="sell"` or `"partner"`, target_sources include masothue, mua_sam_cong,
    query like "công ty logistics tại Đà Nẵng cần chuyển đổi số".
  - E-commerce: `intent="sell"`, target_sources include chotot, facebook, web,
    query like "cửa hàng mỹ phẩm TP.HCM đang tuyển đại lý".
  - Education: `intent="sell"` or `"partner"`, target_sources include topcv, facebook, web,
    query like "trung tâm tiếng Anh tại Hà Nội cần học viên doanh nghiệp".

  **Args:**
  - `query` (string, required): concrete natural-language description of the target leads in Vietnamese or English.
  - `table_id` (string, optional): lead table id if the user already has a table open or named.
  - `locations` (list of strings, optional): city/province names, e.g. `["Hà Nội"]` or `["TP.HCM", "Đà Nẵng"]`.
  - `campaign_id` (string, optional): stable campaign id for tracking / resume.
  - `smoke_test` (boolean, default false): run a cheap preview (limit 5-10) before committing credits.
  - `target_sources` (list of strings, optional): explicit sources. Empty = auto-resolve from query and intent.
  - `target_keywords` (list of strings, optional): positive scoring keywords.
  - `negative_keywords` (list of strings, optional): disqualifying keywords.
  - `min_fit_score` (float, 0-100, default 0): minimum ICP fit score.
  - `enrichment_depth` ("light" | "standard" | "deep", default "standard"): depth of contact/company enrichment.
  - `intent` ("buy" | "sell" | "hire" | "partner" | "invest" | "rent" | "research", default "buy"):
    buying-side intent. Accepts Vietnamese synonyms: "mua", "bán", "tuyển", "hợp tác", "đầu tư", "thuê".
  - `product_type` (string, optional): product or service, e.g. "SaaS", "BĐS", "recruitment", "agency".
  - `price_segment` (string, optional): "premium", "mid-market", "SMB".
  - `preferred_channels` (list of strings, optional): outreach channels, e.g. `["email", "phone", "zalo", "linkedin", "facebook"]`.
  - `limit` (int, 1-200, default 50): maximum leads to return.

  **Returns:** a markdown table with discovered leads plus a persistence summary.
  Present the table, state the source mix, and offer a clear next action (unlock phone,
  draft outreach, save to a table, or optimize criteria).
