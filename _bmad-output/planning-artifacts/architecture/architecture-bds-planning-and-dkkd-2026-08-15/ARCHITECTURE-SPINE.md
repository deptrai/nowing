# Architecture Spine — Real Estate Spatial Planning & National Business Registry Engine

**Ngày lập:** 2026-08-15  
**Trạng thái:** `final`  
**Quyết định Kiến trúc chi phối (Architectural Invariants):** AD-GIS-1 đến AD-GIS-6  
**Epic liên kết:** Epic 24 (Real Estate Spatial GIS & Official Enterprise Verification) & Epic 16  
**Tác giả:** Winston (BMAD System Architect)  

---

## 1. Mục Tiêu & Phạm Vi Hệ Thống

Cung cấp công cụ tra cứu quy hoạch không gian bất động sản (PostGIS Spatial Land Zoning) và hồ sơ pháp lý doanh nghiệp chính thức:
* Tra cứu nhanh thửa đất theo tọa độ GPS/Địa chỉ xem có thuộc diện quy hoạch mở đường (`DGT`), công viên cây xanh (`CX`), hay đất thổ cư (`ONT/ODT`).
* Xác minh pháp lý doanh nghiệp qua Cổng Quốc gia `dangkykinhdoanh.gov.vn`: vốn điều lệ chính thức, danh sách cổ đông, người đại diện pháp luật và lịch sử thay đổi ĐKKD.

---

## 2. Các Quyết Định Kiến Trúc Bắt Buộc (Architectural Invariants)

* **AD-GIS-1 [ADOPTED]: PostGIS Geospatial Polygon Indexing**
  * Kích hoạt `postgis` extension trong PostgreSQL. Toàn bộ ranh giới quy hoạch phân loại đất được lưu trữ dưới dạng `GEOMETRY(MultiPolygon, 4326)` có chỉ mục `GIST` để tính toán giao điểm không gian (`ST_Contains`, `ST_Intersects`) trong $\le 5$ms.
* **AD-GIS-2 [ADOPTED]: Land Classification Code Normalization**
  * Chuẩn hóa toàn bộ mã đất theo quy định của Bộ Tài nguyên & Môi trường: `ODT`, `ONT`, `CLN`, `HNK`, `DGT`, `CX`, `TMD`, `SKC`, `NTS`.
* **AD-GIS-3 [ADOPTED]: Official Business Registry Verification Ingress**
  * Tra cứu trực tiếp Cổng Đăng ký Doanh nghiệp Quốc gia (`dangkykinhdoanh.gov.vn`) bằng Mã số thuế; bóc tách file PDF công bố thay đổi nội dung đăng ký kinh doanh bằng Nowing PDF Parser.
* **AD-GIS-4 [ADOPTED]: Cross-Layer Spatial Enrichment for Real Estate Listings**
  * Tự động liên kết tọa độ tin đăng BĐS cào từ Batdongsan/Chotot/Telegram với bản đồ quy hoạch để gắn nhãn cảnh báo: `"Dính quy hoạch mở đường 20m"` hoặc `"100% Đất ở đô thị"`.
* **AD-GIS-5 [ADOPTED]: Idempotent Enterprise & Spatial Polygon Storage**
  * Khóa duy nhất `tax_code VARCHAR(20)` cho doanh nghiệp và `(province, district, zone_code, polygon_hash)` cho bản đồ quy hoạch.
* **AD-GIS-6 [ADOPTED]: AI Agent Spatial Tools**
  * Đăng ký `realestate_check_zoning(latitude, longitude)` và `enterprise_verify_legal_capital(tax_code)` cho Nowing Agent.

---

## 3. Mô Hình Cơ Sở Dữ Liệu (PostgreSQL + PostGIS DDL)

```sql
-- Kích hoạt extension PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Bảng Bản đồ Quy hoạch Không gian
CREATE TABLE IF NOT EXISTS spatial_planning_zones (
    id BIGSERIAL PRIMARY KEY,
    province VARCHAR(100) NOT NULL,
    district VARCHAR(100),
    ward VARCHAR(100),
    zone_code VARCHAR(20) NOT NULL, -- 'ODT', 'ONT', 'CLN', 'DGT', 'CX', 'TMD'
    zone_name TEXT NOT NULL,
    planning_period VARCHAR(50), -- '2021-2030', '2030-2050'
    polygon_geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
    polygon_hash VARCHAR(64) NOT NULL,
    legal_document_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_spatial_planning_polygon UNIQUE (province, district, zone_code, polygon_hash)
);

CREATE INDEX IF NOT EXISTS idx_spatial_planning_gist ON spatial_planning_zones USING gist (polygon_geometry);
CREATE INDEX IF NOT EXISTS idx_spatial_planning_code ON spatial_planning_zones (zone_code);
CREATE INDEX IF NOT EXISTS idx_spatial_planning_loc ON spatial_planning_zones (province, district);

-- 2. Bảng Hồ sơ Pháp lý Doanh nghiệp Chính thức
CREATE TABLE IF NOT EXISTS official_enterprise_registrations (
    id BIGSERIAL PRIMARY KEY,
    tax_code VARCHAR(20) NOT NULL UNIQUE,
    enterprise_name TEXT NOT NULL,
    legal_representative TEXT,
    charter_capital_vnd NUMERIC(18, 2),
    incorporation_date DATE,
    headquarters_address TEXT,
    shareholders JSONB DEFAULT '[]'::jsonb,
    history_changes JSONB DEFAULT '[]'::jsonb,
    raw_document_urls TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_official_enterprise_tax ON official_enterprise_registrations(tax_code);
CREATE INDEX IF NOT EXISTS idx_official_enterprise_gin_shareholders ON official_enterprise_registrations USING gin (shareholders);
```
