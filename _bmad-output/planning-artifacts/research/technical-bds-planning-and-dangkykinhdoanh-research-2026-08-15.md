# Technical Research — Bản Đồ Quy Hoạch BĐS & Cổng Đăng Ký Kinh Doanh Quốc Gia

**Ngày nghiên cứu:** 2026-08-15  
**Tác giả:** BMAD Technical Research Team  
**Mục tiêu:** Khảo sát chi tiết phương thức khai thác dữ liệu bản đồ quy hoạch không gian (GIS Land Zoning) và dữ liệu pháp lý doanh nghiệp chính thức từ Cổng Quốc gia `dangkykinhdoanh.gov.vn` cho Epic 24 và Epic 16.

---

## 1. Phân hệ 1: Bản Đồ Quy Hoạch Bất Động Sản (Spatial Land Zoning GIS)

### 1.1. Nguồn Dữ liệu & Kiến trúc Bản đồ Không gian
Quy hoạch sử dụng đất tại Việt Nam (kỳ quy hoạch 2021–2030, tầm nhìn 2050) được công bố qua 2 nhóm nguồn:
1. **Cổng Thông tin Quy hoạch Chính quyền cấp Tỉnh/Thành phố:**
   * Hà Nội: `quyhoach.hanoi.vn`, `hanoi.gov.vn`
   * TP. Hồ Chí Minh: `thongtinquyhoach.hochiminhcity.gov.vn`
   * Đà Nẵng, Bình Dương, Đồng Nai: Các cổng GIS địa phương (ArcGIS Server / GeoServer).
2. **Dịch vụ GIS chuyên ngành thương mại (Commercial GIS Data Providers):**
   * **eKMap Land Use Plan API:** Cung cấp REST endpoint tra cứu chức năng sử dụng đất theo tọa độ (`latitude`, `longitude`) hoặc ranh giới polygon.

### 1.2. Kỹ thuật Thu thập & Xử lý Bản đồ (Map Tiles / WFS / GeoJSON)
* **Giao thức:** Web Feature Service (WFS) hoặc Map Tile Matrix (WMTS) trả về các vector polygon phân loại đất:
  * `ONT` / `ODT`: Đất ở nông thôn / Đất ở đô thị (Đất thổ cư giá trị cao nhất).
  * `CLN` / `HNK`: Đất trồng cây lâu năm / Đất trồng cây hàng năm.
  * `DGT`: Đất giao thông (Quy hoạch mở đường, mở rộng lộ giới).
  * `CX`: Đất cây xanh, công viên công cộng.
  * `TMD`: Đất thương mại dịch vụ.
* **Xử lý Không gian trong PostgreSQL:**
  * Kích hoạt extension `PostGIS` (`CREATE EXTENSION IF NOT EXISTS postgis;`).
  * Thực hiện phép toán không gian cực nhanh:
    ```sql
    -- Kiểm tra một tọa độ bất động sản có dính quy hoạch đường giao thông không
    SELECT zone_name, zone_code, description 
    FROM spatial_planning_zones 
    WHERE ST_Contains(polygon_geometry, ST_SetSRID(ST_Point(105.782, 21.031), 4326));
    ```

---

## 2. Phân hệ 2: Cổng Đăng Ký Kinh Doanh Quốc Gia (`dangkykinhdoanh.gov.vn`)

### 2.1. Nguồn Dữ liệu & Giá trị Pháp lý
Khác với `masothue.com` (chỉ có dữ liệu cơ bản mã số thuế), Cổng Đăng Ký Kinh Doanh Quốc Gia (Bộ Kế hoạch & Đầu tư) chứa:
* Danh sách người đại diện theo pháp luật hiện tại và các lần thay đổi lịch sử.
* Danh sách cổ đông sáng lập và tỷ lệ sở hữu vốn góp.
* File PDF Công bố thông tin đăng ký doanh nghiệp (chứa vốn điều lệ chính thức đã nộp).
* Lịch sử các lần thay đổi đăng ký kinh doanh (tăng vốn, đổi địa chỉ, thêm ngành nghề).

### 2.2. Endpoints & Phương thức Tra cứu
* **Tra cứu Doanh nghiệp theo MST:**
  * `GET https://dangkykinhdoanh.gov.vn/vn/Pages/Trangchu.aspx` (khởi tạo ASP.NET ViewState & Session).
  * `POST https://dangkykinhdoanh.gov.vn/Services/EnterpriseSearchService.asmx/SearchEnterprise`
* **Xử lý PDF Công Bố:**
  * Khi doanh nghiệp thay đổi ĐKKD, hệ thống phát hành file PDF thông báo. Celery worker tải file PDF và dùng `app/services/okf/` bóc tách bảng vốn và danh sách cổ đông.

---

## 3. Mô hình Dữ liệu Lưu trữ (PostgreSQL + PostGIS DDL)

```sql
-- Kích hoạt PostGIS
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
    legal_document_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_spatial_planning_geom ON spatial_planning_zones USING gist (polygon_geometry);
CREATE INDEX IF NOT EXISTS idx_spatial_planning_code ON spatial_planning_zones (zone_code);

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

---

## 4. Tích hợp Hệ sinh thái Nowing

1. **AI Agent Tool (`realestate_check_zoning(lat, lng, address)`):** Trả lời ngay câu hỏi: *"Thửa đất tại số 45 Nguyễn Khang có dính quy hoạch mở đường hay công viên cây xanh không?"*.
2. **AI Agent Tool (`enterprise_verify_legal(tax_code)`):** Trả lời câu hỏi: *"Công ty CP Tập đoàn ABC vốn điều lệ bao nhiêu, do ai đại diện pháp luật, có từng bị đổi tên không?"*.
3. **Cross-Linkage với Tin BĐS & Doanh nghiệp:** Tự động đính kèm thông tin quy hoạch vào các tin đăng BĐS cào được từ Batdongsan, Chotot, Telegram.
