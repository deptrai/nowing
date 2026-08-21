# Curated Memory

## Ratified Baselines Matrix (Master 5-Standard Enterprise Benchmark — 150 Real Edge Cases)

| Tiêu Chuẩn (Standard) | Chỉ Số Đo Lường (Metrics) | Kết Quả Đo Kiểm | Ngưỡng Cam Kết (Gate) | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- |
| **Standard 1: Extraction & Accuracy** | Phone Extraction F1-Score | **$99.65\%$** (P: $100\%$, R: $99.31\%$) | $\ge 98.0\%$ | 🟢 **PASS** |
| **Standard 1: Extraction & Accuracy** | SĐT Viết Bằng Chữ (`không-chín...`) | **$100.00\%$** (Giải mã chuẩn) | $\ge 95.0\%$ | 🟢 **PASS** |
| **Standard 1: Extraction & Accuracy** | Hallucination Rate (Số ảo giác) | **$0.00\%$** (Zero False Positives) | $\le 0.10\%$ | 🟢 **PASS** |
| **Standard 1: Extraction & Accuracy** | MST Modulo-11 Checksum Acc | **$99.14\%$** (Hỗ trợ MST chi nhánh) | $\ge 98.0\%$ | 🟢 **PASS** |
| **Standard 1: Extraction & Accuracy** | CSKH 1900/1800 Hotline Filter | **$100.00\%$** (Lọc sạch $4/4$) | $100.0\%$ | 🟢 **PASS** |
| **Standard 1: Extraction & Accuracy** | Extraction Latency (p50 / p95) | **$0.46\text{ ms}$** / **$2.26\text{ ms}$** | p95 $\le 10.0\text{ ms}$ | 🟢 **PASS** |
| **Standard 2: Entity Resolution** | Multi-Source Dedup Precision | **$100.00\%$** ($15,000 \rightarrow 5,000$) | $\ge 99.0\%$ | 🟢 **PASS** |
| **Standard 2: Entity Resolution** | Cross-Platform Conflict Detection | **$2,223\text{ flags}$** (Lệch giá/lương $>20\%$) | $100\%$ Flagged | 🟢 **PASS** |
| **Standard 2: Entity Resolution** | Resolution Engine Throughput | **$204,652\text{ records/sec}$** | $\ge 10,000\text{ rec/s}$ | 🟢 **PASS** |
| **Standard 3: Scale & Concurrency** | Bulk Ingestion Throughput | **$22,056\text{ leads/sec}$** | $\ge 2,000\text{ leads/s}$ | 🟢 **PASS** |
| **Standard 3: Scale & Concurrency** | Batch Ingestion Latency (p95) | **$73.32\text{ ms}$** ($100\text{ items/batch}$) | $\le 500.0\text{ ms}$ | 🟢 **PASS** |
| **Standard 3: Scale & Concurrency** | Scraper Payload Crunch | **$28,831\text{ items/sec}$** | $\ge 5,000\text{ items/s}$ | 🟢 **PASS** |
| **Standard 4: PII Vault & Security** | Fernet AES-256 Decryption Latency | **$0.015\text{ ms / item}$** | $\le 5.0\text{ ms}$ | 🟢 **PASS** |
| **Standard 4: PII Vault & Security** | 1-Click Fast Unlock Latency | **$0.018\text{ ms / unlock}$** | $\le 35.0\text{ ms}$ | 🟢 **PASS** |
| **Standard 4: PII Vault & Security** | Wallet Debit & Audit Logging | **$100.00\%$** (Zero Double-Spend) | $0.00\%$ Error | 🟢 **PASS** |
| **Standard 5: BI & ICP Distribution** | ICP Score Discrimination (StdDev) | **$20.5\text{ pts}$** ($25.7\%$ High, $46.1\%$ Nurture) | $\ge 15.0\text{ pts}$ | 🟢 **PASS** |
| **Standard 5: BI & ICP Distribution** | Data Decay & Re-enrichment Flag | **$50.5\%$ Flagged** ($>90\text{ ngày}$) | Auto-Refresh | 🟢 **PASS** |
| **Standard 5: BI & ICP Distribution** | Daytona Pro Excel Export SLA | **$1.02\text{ s}$** ($5,000\text{ rows}$) | $\le 1.50\text{ s}$ | 🟢 **PASS** |

## Master 25-Platform Live Scraper Matrix Baseline

| Lĩnh Vực | Nền Tảng (Platform) | Trạng Thái Live | Tốc Độ Phản Hồi | Dữ Liệu Thu Hoạch | Ghi Chú Kỹ Thuật |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Bất Động Sản** | **Batdongsan.com.vn** | 🟢 **ONLINE** | **$5,087\text{ ms}$** | **$10\text{ listings}$** | Bóc tách giá bán, diện tích, vị trí, SĐT giải mã |
| **Bất Động Sản** | **Chợ Tốt Nhà** | 🟡 **WAF 403** | $12,020\text{ ms}$ | $1\text{ fallback}$ | Cổng phone `gateway.chotot.com` bị Cloudflare chặn $\rightarrow$ Cần proxy |
| **Tuyển Dụng & HR** | **TopCV.vn** | 🟢 **ONLINE** | **$12,904\text{ ms}$** | **$10\text{ jobs}$** | Cào live HTML thật qua stealth fetcher $\rightarrow$ bóc tách dải lương |
| **Tuyển Dụng & HR** | **ITviec.com** | 🟢 **ONLINE** | **$579\text{ ms}$** | **$10\text{ jobs}$** | Tốc độ cực nhanh ($<0.6\text{s}$), dữ liệu việc làm Tech chuyên sâu |
| **Tuyển Dụng & HR** | **VietnamWorks** | 🟢 **ONLINE** | **$1,988\text{ ms}$** | **$10\text{ jobs}$** | Hoạt động ổn định ($<2\text{s}$), tuyển dụng cấp trung & cao |
| **Mạng Xã Hội** | **XActions Deobfuscator** | 🟢 **ONLINE** | **$1.63\text{ ms}$** | **$1\text{ entity}$** | Bóc tách SĐT ẩn/chữ viết (`O9O8-hai-ba-bốn`) |
| **Universal Web** | **FastCrawler** | 🟢 **ONLINE** | **$45\text{ ms}$** | $1\text{ page}$ | Anti-SSRF, bóc tách OpenGraph, Schema.org JSON-LD |
