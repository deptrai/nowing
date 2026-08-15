# Story 10.8: Spatial Planning & Land Zoning GIS (PostGIS Map Layers)

Status: in-progress

<!-- Governed by architecture-bds-planning-and-dkkd-2026-08-15 (AD-GIS-1 to AD-GIS-7) and UX Widget U5 -->

## Story

As a real estate investor, broker, or valuation analyst,
I want to query spatial land zoning information and master planning boundaries (Quy hoạch sử dụng đất) for any coordinate in Vietnam,
So that I can verify land usability (Đất ở ODT/ONT vs Đất giao thông DGT mở đường) with $\le 10$ms latency before acquiring property leads.

## Acceptance Criteria

1. **Given** spatial planning GeoJSON / Shapefile datasets, **When** ingested into PostgreSQL/PostGIS, **Then** polygons are stored in `spatial_planning_zones` as `GEOMETRY(MultiPolygon, 4326)` after running `ST_MakeValid()` and `ST_Subdivide()`, indexed with a spatial GIST index (AD-GIS-1, AD-GIS-3).
2. **Given** a latitude and longitude coordinate `(lat, lng)`, **When** `SpatialPlanningService` queries land zoning, **Then** it validates coordinate bounds ($102.0 \le \text{lng} \le 109.5$, $8.5 \le \text{lat} \le 23.5$), detects inverted/swapped coordinates, constructs `ST_MakePoint(lng, lat, 4326)`, and returns intersecting planning zones via `ST_Intersects` with response latency $\le 10$ms (AD-GIS-2, AD-GIS-4).
3. **Given** intersecting planning zones, **When** formatted for display, **Then** zone codes are categorized with clear polarity: `ODT`/`ONT` (Đất ở - Green polarity), `DGT` (Đất giao thông/Quy hoạch mở đường - Red warning polarity, `has_road_expansion_risk=True`), `TMD`/`SKC` (Đất thương mại/sản xuất - Blue polarity), `CX` (Đất cây xanh - Yellow/Orange polarity) (AD-GIS-5, Widget U5).
4. **Given** a user viewing property details in Nowing Web, **When** opening the Land Zoning Modal (Widget U5), **Then** an interactive Mapbox/Leaflet vector overlay renders the exact cadastral boundary and zoning metadata.
5. **Given** an AI Agent session, **When** calling `nowing_realestate_check_zoning(latitude, longitude)`, **Then** the agent returns the exact land zoning classification, road clearance risk, and legal planning note (AD-GIS-6).

## Architectural Invariants Mapping

- **AD-GIS-1**: PostGIS Spatial Geometry Schema (`GEOMETRY(MultiPolygon, 4326)` with GIST Index `idx_spatial_planning_gist`)
- **AD-GIS-2**: Longitude-Latitude Coordinate Ordering Invariant (`ST_MakePoint(lng, lat, 4326)`)
- **AD-GIS-3**: Geometry Simplification & Validity Pipeline (`ST_MakeValid` + `ST_Subdivide` + VN-2000 to WGS84 Transformer)
- **AD-GIS-4**: Sub-10ms Fast Spatial Intersect Query Engine (`ST_Intersects`)
- **AD-GIS-5**: Road Clearance & Zoning Risk Detection (`DGT` Warning Flag)
- **AD-GIS-6**: AI Agent Capability Tool (`nowing_realestate_check_zoning` / `realestate.zoning`)
- **AD-GIS-7**: Land Zoning Modal UX Contract with Polarity Colors (Widget U5)

## Tasks / Subtasks

- [x] Task 1: PostGIS Database Schema & Geometry Models (AC: 1, 2)
  - [x] 1.1 Tạo model `SpatialPlanningZone` trong `nowing_backend/app/proprietary/platforms/spatial_planning/models.py` (`id`, `province`, `district`, `ward`, `zone_code`, `zone_name`, `planning_period`, `effective_year`, `expiry_year`, `polygon_geometry Geometry(MULTIPOLYGON, 4326)`, `polygon_hash VARCHAR(64)`, `legal_document_ref`, `created_at`, `CONSTRAINT uq_spatial_planning_polygon UNIQUE (province, district, zone_code, polygon_hash)`).
  - [x] 1.2 Tạo spatial GIST index `idx_spatial_planning_gist` trên cột `polygon_geometry` và btree index trên `zone_code`, `(province, district)`.
- [x] Task 2: Spatial Planning Service & ST_Intersects Engine (AC: 2, 3)
  - [x] 2.1 Xây dựng `SpatialPlanningService` tại `nowing_backend/app/proprietary/platforms/spatial_planning/service.py`.
  - [x] 2.2 Viết hàm `validate_coordinates(lat: float, lng: float)` kiểm tra giới hạn tọa độ VN ($102.0 \le \text{lng} \le 109.5, 8.5 \le \text{lat} \le 23.5$) và phát hiện đảo ngược tọa độ.
  - [x] 2.3 Viết hàm `check_zoning(lat: float, lng: float)` truy vấn `ST_Intersects(polygon_geometry, ST_SetSRID(ST_MakePoint(lng, lat), 4326))`.
  - [x] 2.4 Phân loại cảnh báo rủi ro (đánh dấu `has_road_expansion_risk = True` khi có zone `DGT`, phân loại polarity `safe`, `danger`, `warning`, `commercial`).
- [x] Task 3: GeoJSON / Shapefile Ingestion Pipeline (AC: 1)
  - [x] 3.1 Xây dựng `PlanningDataImporter` tại `nowing_backend/app/proprietary/platforms/spatial_planning/importer.py` hỗ trợ đọc GeoJSON/Shapefile, chuyển đổi VN-2000 $\rightarrow$ WGS-84 (SRID 4326) qua `pyproj` và `shapely`.
  - [x] 3.2 Tự động chuẩn hóa `MultiPolygon`, `shapely.make_valid()` và tính hash SHA-256 chống trùng lặp.
- [x] Task 4: AI Agent Capability & Tools (AC: 5)
  - [x] 4.1 Đăng ký Capability `realestate.zoning` trong `nowing_backend/app/capabilities/realestate/zoning/definition.py`.
  - [x] 4.2 Định nghĩa Agent Tool `nowing_realestate_check_zoning` phục vụ AI Agent và đăng ký trong `mcp_tools.py`.
- [x] Task 5: Unit & Integration Tests (AC: 1-5)
  - [x] 5.1 `tests/unit/proprietary/platforms/spatial_planning/test_coordinate_validation.py` (Kiểm tra bounds tọa độ và đảo thứ tự lng/lat).
  - [x] 5.2 `tests/unit/proprietary/platforms/spatial_planning/test_planning_service.py` (Mock spatial query, risk flags, polarity).
  - [x] 5.3 `tests/unit/capabilities/test_realestate_zoning_capabilities.py` (Capability schemas, executor, tool registration).

## Dev Notes

- **Coordinate Order Invariant:** PostGIS `ST_MakePoint(X, Y)` nhận `(Longitude, Latitude)`. Luôn kiểm tra $102.0 \le \text{lng} \le 109.5$ và $8.5 \le \text{lat} \le 23.5$.
- **Dependencies:** `geoalchemy2>=0.15.0`, `shapely>=2.0.0`, `pyproj>=3.6.0`.

### References
- [Architecture Spine: architecture-bds-planning-and-dkkd-2026-08-15/ARCHITECTURE-SPINE.md]
- [UX Contract: ux-contract-scrapers-expansion-and-lead-intelligence.md#U5]
