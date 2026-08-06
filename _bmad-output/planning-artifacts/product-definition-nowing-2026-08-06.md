---
title: "Nowing — Product Definition"
project: Nowing
date: 2026-08-06
author: Paige (Technical Writer)
status: final
---

# Nowing

## Tagline

> **"From data to knowing."**

---

## What is Nowing?

**Nowing** (now + knowing) là knowledge intelligence platform — nơi raw data từ mọi nguồn biến thành kiến thức thực sự.

Khác biệt giữa data và kiến thức:

- **Data** là "căn hộ Thủ Đức 3.5 tỷ trên Batdongsan"
- **Data** là "căn hộ Thủ Đức 3.2 tỷ trên Chotot"
- **Data** là "căn hộ Thủ Đức 4.1 tỷ trên Muaban"

Ba cái data. Ba con số khác nhau. Bạn không biết tin cái nào.

**Kiến thức** là: "Căn hộ Thủ Đức này đang được rao bán với giá trung bình 3.6 tỷ, trải dài từ 3.2–4.1 tỷ qua 3 nguồn, và giá đã tăng 8% trong 2 tháng qua."

**Nowing biến data thành kiến thức.**

---

## Three Transformations

### 1. Data → Entity

Mỗi nguồn nói về cùng một thứ theo cách khác nhau. Nowing nhận ra đó là cùng một entity — cùng một căn hộ, cùng một công ty, cùng một sản phẩm — và gộp chúng lại.

Không phải "ba kết quả tìm kiếm". Là **một entity** với nhiều nguồn.

### 2. Entity → Knowledge

Entity đơn lẻ chưa phải kiến thức. Kiến thức là khi bạn biết:

- Giá trị thực là gì (dedup + confidence score)
- Độ tin cậy ra sao (source count + provenance)
- Nó thay đổi thế nào theo thời gian (temporal tracking)
- Nó liên quan đến gì khác (relations)

### 3. Knowledge → Memory

Kiến thức mất đi khi bạn quên. Nowing nhớ cho bạn — không chỉ cái bạn vừa tìm, mà cả cách nó thay đổi. Lần sau bạn cần biết, Nowing trả về delta: cái mới, cái khác, cái mất.

---

## The Name

**Nowing** = **Now** + **Knowing**

- **Now** — dữ liệu real-time, không phải static database
- **Nowing** — quá trình trở thành người biết, người có kiến thức

Không phải "tìm kiếm" (search). Không phải "lưu trữ" (storage). Là **"knowing"** — trạng thái của việc biết và hiểu.

---

## The Promise

> Bạn không cần sở hữu mọi dữ liệu.
> Bạn cần **hiểu** dữ liệu.

> Nowing không cho bạn thêm tab.
> Nowing cho bạn **kiến thức**.

---

## Who Uses Nowing

| User | What they do |
|------|-------------|
| **Nhà đầu tư BĐS** | Track giá nhà khắp các sàn, nhận alert khi có thay đổi |
| **HR Analyst** | Benchmark lương cross-platform, theo dõi xu hớng tuyển dụng |
| **Product Researcher** | So sánh giá sản phẩm trên Lazada/Shopee, track competitor |
| **Nhà nghiên cứu** | Tổng hợp dữ liệu từ news + finance + company data, không duplicate |
| **AI Agent Builder** | Gọi MCP tools để research thay vì tự scrape web |

---

## What Makes Nowing Different

| | Others | Nowing |
|---|--------|--------|
| **Data model** | Document-centric | Entity-centric |
| **Duplicates** | Show all | Dedup into golden records |
| **Trust** | No source link | Citations on every fact |
| **History** | Snapshot only | Temporal tracking |
| **Search** | Single-source | Unified across all sources |
| **Privacy** | Cloud-only, vendor lock-in | Self-host, data ownership |
| **API** | Human-only UI | MCP tools for AI agents |

---

## Data Strategy (3 Layers)

| Layer | What | Count | Maintain |
|-------|------|-------|----------|
| **Built-in Scrapers** | High-value structured sources | 30-50 max | Nowing team |
| **User Connectors** | OAuth personal data | Unlimited | 0 (official APIs) |
| **Generic Web Crawl** | ChainLens arbitrary URLs | Unlimited | 0 (ChainLens) |

**Nowing does NOT build scrapers for millions of websites.** Expansion happens through OAuth connectors and ChainLens, not more built-in scrapers.

---

**Document Status:** Final
**Author:** Paige (Technical Writer)
