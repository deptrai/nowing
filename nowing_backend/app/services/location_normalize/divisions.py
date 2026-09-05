"""Vietnamese Administrative Divisions Catalog (Story 26.25).

Provides structured province and district mappings with diacritic-tolerant
search and canonical GSO/TCTK codes.
"""

from __future__ import annotations

from typing import TypedDict


class DistrictRecord(TypedDict, total=False):
    code: str
    name: str
    wards: list[str]


class ProvinceRecord(TypedDict):
    code: str
    name: str
    aliases: list[str]
    districts: list[DistrictRecord]


PROVINCES_DATA: list[ProvinceRecord] = [
    {
        "code": "HN",
        "name": "Hà Nội",
        "aliases": ["hanoi", "ha-noi", "hn"],
        "districts": [
            {"code": "001", "name": "Ba Đình"},
            {"code": "002", "name": "Hoàn Kiếm"},
            {"code": "003", "name": "Tây Hồ"},
            {"code": "004", "name": "Long Biên"},
            {"code": "005", "name": "Cầu Giấy"},
            {"code": "006", "name": "Đống Đa"},
            {"code": "007", "name": "Hai Bà Trưng"},
            {"code": "008", "name": "Hoàng Mai"},
            {"code": "009", "name": "Thanh Xuân"},
            {"code": "016", "name": "Sóc Sơn"},
            {"code": "017", "name": "Đông Anh"},
            {"code": "018", "name": "Gia Lâm"},
            {"code": "019", "name": "Nam Từ Liêm"},
            {"code": "020", "name": "Thanh Trì"},
            {"code": "021", "name": "Bắc Từ Liêm"},
            {"code": "268", "name": "Hà Đông"},
            {"code": "269", "name": "Sơn Tây"},
            {"code": "271", "name": "Ba Vì"},
            {"code": "272", "name": "Phúc Thọ"},
            {"code": "273", "name": "Đan Phượng"},
            {"code": "274", "name": "Hoài Đức"},
            {"code": "275", "name": "Quốc Oai"},
            {"code": "276", "name": "Thạch Thất"},
            {"code": "277", "name": "Chương Mỹ"},
            {"code": "278", "name": "Thanh Oai"},
            {"code": "279", "name": "Thường Tín"},
            {"code": "280", "name": "Phú Xuyên"},
            {"code": "281", "name": "Ứng Hòa"},
            {"code": "282", "name": "Mỹ Đức"},
        ],
    },
    {
        "code": "SG",
        "name": "TP. Hồ Chí Minh",
        "aliases": ["saigon", "sai-gon", "hcm", "tphcm", "ho-chi-minh", "sg"],
        "districts": [
            {"code": "760", "name": "Quận 1"},
            {"code": "761", "name": "Quận 12"},
            {"code": "764", "name": "Gò Vấp"},
            {"code": "765", "name": "Bình Thạnh"},
            {"code": "766", "name": "Tân Bình"},
            {"code": "767", "name": "Tân Phú"},
            {"code": "768", "name": "Phú Nhuận"},
            {"code": "769", "name": "Thành phố Thủ Đức"},
            {"code": "770", "name": "Quận 3"},
            {"code": "771", "name": "Quận 10"},
            {"code": "772", "name": "Quận 11"},
            {"code": "773", "name": "Quận 4"},
            {"code": "774", "name": "Quận 5"},
            {"code": "775", "name": "Quận 6"},
            {"code": "776", "name": "Quận 8"},
            {"code": "777", "name": "Bình Tân"},
            {"code": "778", "name": "Quận 7"},
            {"code": "783", "name": "Củ Chi"},
            {"code": "784", "name": "Hóc Môn"},
            {"code": "785", "name": "Bình Chánh"},
            {"code": "786", "name": "Nhà Bè"},
            {"code": "787", "name": "Cần Giờ"},
        ],
    },
    {
        "code": "DN",
        "name": "Đà Nẵng",
        "aliases": ["danang", "da-nang", "dn"],
        "districts": [
            {"code": "490", "name": "Liên Chiểu"},
            {"code": "491", "name": "Thanh Khê"},
            {"code": "492", "name": "Hải Châu"},
            {"code": "493", "name": "Sơn Trà"},
            {"code": "494", "name": "Ngũ Hành Sơn"},
            {"code": "495", "name": "Cẩm Lệ"},
            {"code": "497", "name": "Hòa Vang"},
            {"code": "498", "name": "Hoàng Sa"},
        ],
    },
    {
        "code": "HP",
        "name": "Hải Phòng",
        "aliases": ["haiphong", "hai-phong", "hp"],
        "districts": [
            {"code": "303", "name": "Hồng Bàng"},
            {"code": "304", "name": "Ngô Quyền"},
            {"code": "305", "name": "Lê Chân"},
            {"code": "306", "name": "Hải An"},
            {"code": "307", "name": "Kiến An"},
            {"code": "308", "name": "Đồ Sơn"},
            {"code": "309", "name": "Dương Kinh"},
            {"code": "311", "name": "Thủy Nguyên"},
            {"code": "312", "name": "An Dương"},
            {"code": "313", "name": "An Lão"},
            {"code": "314", "name": "Kiến Thụy"},
            {"code": "315", "name": "Tiên Lãng"},
            {"code": "316", "name": "Vĩnh Bảo"},
            {"code": "317", "name": "Cát Hải"},
            {"code": "318", "name": "Bạch Long Vĩ"},
        ],
    },
    {
        "code": "CT",
        "name": "Cần Thơ",
        "aliases": ["cantho", "can-tho", "ct"],
        "districts": [
            {"code": "916", "name": "Ninh Kiều"},
            {"code": "917", "name": "Ô Môn"},
            {"code": "918", "name": "Bình Thủy"},
            {"code": "919", "name": "Cái Răng"},
            {"code": "923", "name": "Thốt Nốt"},
            {"code": "924", "name": "Vĩnh Thạnh"},
            {"code": "925", "name": "Cờ Đỏ"},
            {"code": "926", "name": "Phong Điền"},
            {"code": "927", "name": "Thới Lai"},
        ],
    },
    {
        "code": "BD",
        "name": "Bình Dương",
        "aliases": ["binhduong", "binh-duong", "bd"],
        "districts": [
            {"code": "718", "name": "Thủ Dầu Một"},
            {"code": "719", "name": "Bàu Bàng"},
            {"code": "720", "name": "Dầu Tiếng"},
            {"code": "721", "name": "Bến Cát"},
            {"code": "722", "name": "Phú Giáo"},
            {"code": "723", "name": "Tân Uyên"},
            {"code": "724", "name": "Dĩ An"},
            {"code": "725", "name": "Thuận An"},
            {"code": "726", "name": "Bắc Tân Uyên"},
        ],
    },
    {
        "code": "DNA",
        "name": "Đồng Nai",
        "aliases": ["dongnai", "dong-nai"],
        "districts": [
            {"code": "731", "name": "Biên Hòa"},
            {"code": "732", "name": "Long Khánh"},
            {"code": "734", "name": "Tân Phú"},
            {"code": "735", "name": "Vĩnh Cửu"},
            {"code": "736", "name": "Định Quán"},
            {"code": "737", "name": "Trảng Bom"},
            {"code": "738", "name": "Thống Nhất"},
            {"code": "739", "name": "Cẩm Mỹ"},
            {"code": "740", "name": "Long Thành"},
            {"code": "741", "name": "Xuân Lộc"},
            {"code": "742", "name": "Nhơn Trạch"},
        ],
    },
    {
        "code": "VT",
        "name": "Bà Rịa - Vũng Tàu",
        "aliases": ["vungtau", "vung-tau", "ba-ria", "vt"],
        "districts": [
            {"code": "747", "name": "Vũng Tàu"},
            {"code": "748", "name": "Bà Rịa"},
            {"code": "750", "name": "Châu Đức"},
            {"code": "751", "name": "Xuyên Mộc"},
            {"code": "752", "name": "Long Điền"},
            {"code": "753", "name": "Đất Đỏ"},
            {"code": "754", "name": "Phú Mỹ"},
            {"code": "755", "name": "Côn Đảo"},
        ],
    },
    {
        "code": "KH",
        "name": "Khánh Hòa",
        "aliases": ["nhatrang", "nha-trang", "khanh-hoa"],
        "districts": [
            {"code": "568", "name": "Nha Trang"},
            {"code": "569", "name": "Cam Ranh"},
            {"code": "570", "name": "Cam Lâm"},
            {"code": "571", "name": "Vạn Ninh"},
            {"code": "572", "name": "Ninh Hòa"},
            {"code": "573", "name": "Khánh Vĩnh"},
            {"code": "574", "name": "Diên Khánh"},
            {"code": "575", "name": "Khánh Sơn"},
            {"code": "576", "name": "Trường Sa"},
        ],
    },
    {
        "code": "LD",
        "name": "Lâm Đồng",
        "aliases": ["dalat", "da-lat", "lam-dong"],
        "districts": [
            {"code": "672", "name": "Đà Lạt"},
            {"code": "673", "name": "Bảo Lộc"},
            {"code": "674", "name": "Đam Rông"},
            {"code": "675", "name": "Lạc Dương"},
            {"code": "676", "name": "Lâm Hà"},
            {"code": "677", "name": "Đơn Dương"},
            {"code": "678", "name": "Đức Trọng"},
            {"code": "679", "name": "Di Linh"},
            {"code": "680", "name": "Bảo Lâm"},
            {"code": "681", "name": "Đạ Huoai"},
            {"code": "682", "name": "Đạ Tẻh"},
            {"code": "683", "name": "Cát Tiên"},
        ],
    },
]


def get_all_provinces() -> list[dict[str, str]]:
    """Return all available provinces as code/name pairs."""
    return [{"code": p["code"], "name": p["name"]} for p in PROVINCES_DATA]


def get_districts_by_province(province_code: str) -> list[DistrictRecord]:
    """Return all districts for a given province code or alias."""
    if not province_code:
        return []
    p_code = province_code.upper().strip()
    for p in PROVINCES_DATA:
        if p["code"] == p_code:
            return [dict(d) for d in p["districts"]]

    # Fallback to check alias
    p_code_lower = province_code.lower().strip()
    for p in PROVINCES_DATA:
        if any(alias == p_code_lower for alias in p["aliases"]):
            return [dict(d) for d in p["districts"]]

    return []


def format_location_summary(
    province_code: str,
    district_codes: list[str] | None = None,
    ward_names: list[str] | None = None,
) -> str:
    """Produce a human-readable location string like 'TP. Hồ Chí Minh (Quận 1, Thủ Đức)'."""
    if not province_code:
        return ""
    p_code = province_code.upper().strip()
    target_prov = next((p for p in PROVINCES_DATA if p["code"] == p_code), None)
    if not target_prov:
        p_code_lower = province_code.lower().strip()
        target_prov = next(
            (p for p in PROVINCES_DATA if any(alias == p_code_lower for alias in p["aliases"])),
            None,
        )
    if not target_prov:
        return province_code

    p_name = target_prov["name"]
    d_codes = set(district_codes or [])
    selected_districts = [
        d["name"] for d in target_prov["districts"] if d["code"] in d_codes
    ]

    parts: list[str] = []
    if selected_districts:
        parts.extend(selected_districts)
    if ward_names:
        parts.extend([w.strip() for w in ward_names if w and w.strip()])

    if parts:
        return f"{p_name} ({', '.join(parts)})"
    return p_name

