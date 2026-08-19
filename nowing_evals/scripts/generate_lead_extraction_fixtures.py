#!/usr/bin/env python3
"""Generate 100 valid lead-extraction fixtures and golden cassettes for Story 26.7."""

from __future__ import annotations

import json
import random
from pathlib import Path

# Ensure reproducible output
random.seed(26_7)

_WEIGHTS = [31, 29, 23, 19, 17, 13, 7, 5, 3]
_PHONE_PREFIXES = ["090", "091", "093", "097", "098", "099", "032", "033", "034", "035", "036", "037", "038", "039"]
_COMPANY_TYPES = [
    "CÔNG TY TNHH",
    "CÔNG TY CỔ PHẦN",
    "DOANH NGHIỆP TƯ NHÂN",
    "TẬP ĐOÀN CÔNG NGHỆ",
    "TỔNG CÔNG TY",
    "HỢP TÁC XÃ",
    "CÔNG TY TNHH MTV",
]


def _mst_check_digit(prefix: str) -> int:
    digits = [int(c) for c in prefix]
    checksum = sum(d * w for d, w in zip(digits, _WEIGHTS, strict=True))
    remainder = checksum % 11
    check = 10 - remainder
    if check == 10:
        check = 0
    return check


def _generate_valid_tax_id() -> str:
    # 10 digits, start with 010 to avoid phone-like prefixes; keyword context in source keeps it safe anyway
    prefix = "010" + "".join(str(random.randint(0, 9)) for _ in range(6))
    return prefix + str(_mst_check_digit(prefix))


def _generate_phone() -> str:
    return random.choice(_PHONE_PREFIXES) + "".join(str(random.randint(0, 9)) for _ in range(7))


def _normalize_phone(phone: str) -> str:
    return phone  # generated phones are already 10-digit 0xxx


def _generate_case(case_id: int) -> dict:
    tax_id = _generate_valid_tax_id()
    phone = _generate_phone()
    company_type = random.choice(_COMPANY_TYPES)
    company_name = f"{company_type} Kiểm thử {case_id:03d}"

    # Source text variations to exercise normalization/delimiters
    templates = [
        "{company_name}. Mã số thuế: {tax_id}. Liên hệ: {phone}.",
        "{company_name} - MST {tax_id} - Hotline {phone}",
        "Tuyển dụng {company_name}. Mã số thuế {tax_id}. SĐT {phone}",
        "{company_name}; Tax ID: {tax_id}; phone {phone}",
        "Công ty {company_name} thông báo: MST {tax_id}, liên hệ {phone}",
        "{company_name}. Mã số DN {tax_id}. ĐT: {phone}",
        "{company_name} | Mã số thuế: {tax_id} | Hotline: {phone}",
    ]
    source = random.choice(templates).format(company_name=company_name, tax_id=tax_id, phone=phone)

    return {
        "case_id": f"lead-{case_id:03d}",
        "source_markdown": source,
        "expected_phones": [phone],
        "expected_tax_ids": [tax_id],
        "expected_tax_ids_valid": [True],
        "expected_company_name": company_name,
        "tags": ["synthetic", f"batch-{((case_id - 1) // 20) + 1}"],
    }


def _cassette_body(case: dict) -> dict:
    return {
        "phones": case["expected_phones"],
        "tax_ids": case["expected_tax_ids"],
        "tax_ids_valid": case["expected_tax_ids_valid"],
        "company_name": case["expected_company_name"],
    }


def main() -> None:
    base = Path(__file__).parent.parent / "data" / "lead_extraction" / "regression"
    cassettes_dir = base / "cassettes"
    default_cases_path = Path(__file__).parent.parent / "src" / "nowing_evals" / "suites" / "lead_extraction" / "regression" / "default_cases.jsonl"

    base.mkdir(parents=True, exist_ok=True)
    cassettes_dir.mkdir(parents=True, exist_ok=True)

    # Keep the original 10 hand-crafted cases plus generate 90 more to reach 100
    original_cases = [
        {
            "case_id": "lead-001",
            "source_markdown": "Công ty TNHH Viễn Thông ABC. MST: 0100109106. Hotline: 0908123456 hoặc O912.345.678.",
            "expected_phones": ["0908123456", "0912345678"],
            "expected_tax_ids": ["0100109106"],
            "expected_tax_ids_valid": [True],
            "expected_company_name": "Công ty TNHH Viễn Thông ABC",
            "tags": ["telecom", "obfuscated-phone"],
        },
        {
            "case_id": "lead-002",
            "source_markdown": "TẬP ĐOÀN CÔNG NGHỆ FPT. Chi nhánh HCM: 0300588569-001. Alo ngay +84 987 654 321 gặp phòng kinh doanh.",
            "expected_phones": ["0987654321"],
            "expected_tax_ids": ["0300588569-001"],
            "expected_tax_ids_valid": [True],
            "expected_company_name": "TẬP ĐOÀN CÔNG NGHỆ FPT",
            "tags": ["tech", "branch-mst", "prefix-84"],
        },
        {
            "case_id": "lead-003",
            "source_markdown": "Chính chủ cho thuê nhà xưởng. Liên hệ anh Nam: 09 12 34 56 78. Không tiếp môi giới.",
            "expected_phones": ["0912345678"],
            "expected_tax_ids": [],
            "expected_tax_ids_valid": [],
            "expected_company_name": None,
            "tags": ["real-estate", "spaced-digits"],
        },
        {
            "case_id": "lead-004",
            "source_markdown": "DOANH NGHIỆP TƯ NHÂN MINH PHÁT. Mã số thuế: 0100109106. SĐT Zalo 84908889999.",
            "expected_phones": ["0908889999"],
            "expected_tax_ids": ["0100109106"],
            "expected_tax_ids_valid": [True],
            "expected_company_name": "DOANH NGHIỆP TƯ NHÂN MINH PHÁT",
            "tags": ["manufacturing", "zalo-84"],
        },
        {
            "case_id": "lead-005",
            "source_markdown": "Tuyển dụng nhân viên kinh doanh bất động sản. Hotline o79-888-9999 gặp Chị Hương.",
            "expected_phones": ["0798889999"],
            "expected_tax_ids": [],
            "expected_tax_ids_valid": [],
            "expected_company_name": None,
            "tags": ["recruitment", "letter-o"],
        },
        {
            "case_id": "lead-006",
            "source_markdown": "Công ty Cổ phần Xây dựng Delta. Mã số thuế 0300588569. Liên hệ số cũ 01681234567.",
            "expected_phones": ["0381234567"],
            "expected_tax_ids": ["0300588569"],
            "expected_tax_ids_valid": [True],
            "expected_company_name": "Công ty Cổ phần Xây dựng Delta",
            "tags": ["construction", "legacy-11-digit"],
        },
        {
            "case_id": "lead-007",
            "source_markdown": "Bán gấp lô đất mặt tiền quận 9. Gọi ngay o93.456.7890 hoặc nhắn tin Zalo.",
            "expected_phones": ["0934567890"],
            "expected_tax_ids": [],
            "expected_tax_ids_valid": [],
            "expected_company_name": None,
            "tags": ["real-estate", "obfuscated-dot"],
        },
        {
            "case_id": "lead-008",
            "source_markdown": "CÔNG TY TNHH GIẢI PHÁP SỐ. MST: 0100109106. Email: contact@digital.vn. SĐT: 0988776655.",
            "expected_phones": ["0988776655"],
            "expected_tax_ids": ["0100109106"],
            "expected_tax_ids_valid": [True],
            "expected_company_name": "CÔNG TY TNHH GIẢI PHÁP SỐ",
            "tags": ["tech", "full-profile"],
        },
        {
            "case_id": "lead-009",
            "source_markdown": "Mã số doanh nghiệp: 0300588569. Cảnh báo lừa đảo liên hệ 0911223344.",
            "expected_phones": ["0911223344"],
            "expected_tax_ids": ["0300588569"],
            "expected_tax_ids_valid": [True],
            "expected_company_name": None,
            "tags": ["fraud", "valid-mst"],
        },
        {
            "case_id": "lead-010",
            "source_markdown": "Tuyển lập trình viên Python / FastAPI lương $2000. CV gửi về hr@nowing.net hoặc gọi 0909000111.",
            "expected_phones": ["0909000111"],
            "expected_tax_ids": [],
            "expected_tax_ids_valid": [],
            "expected_company_name": None,
            "tags": ["tech-recruitment"],
        },
    ]

    cases = original_cases[:]
    for i in range(11, 101):
        cases.append(_generate_case(i))

    # Write default_cases.jsonl in package
    default_cases_path.parent.mkdir(parents=True, exist_ok=True)
    with default_cases_path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + "\n")

    # Write cassettes for every case
    for case in cases:
        cassette_path = cassettes_dir / f"{case['case_id']}.sse.jsonl"
        body = _cassette_body(case)
        with cassette_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "rest", "status": 200, "headers": {}, "body": body}, ensure_ascii=False) + "\n")

    print(f"Wrote {len(cases)} cases to {default_cases_path}")
    print(f"Wrote {len(cases)} cassettes to {cassettes_dir}")


if __name__ == "__main__":
    main()
