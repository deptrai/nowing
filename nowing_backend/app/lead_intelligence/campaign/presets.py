"""Vertical Presets and Reverse-ICP Intelligence for Campaign Builder (Story 25.5 / Signal-First UX)."""

from __future__ import annotations

import re
import urllib.parse
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.lead_intelligence.adapters.base import LeadSourceCategory
from app.lead_intelligence.campaign.schemas import ICPCriteria, SourceBudget


class VerticalPresetId(StrEnum):
    """Supported vertical templates for Campaign Builder."""

    B2B_SAAS = "b2b_saas"
    REAL_ESTATE_INVESTOR = "real_estate_investor"
    RECRUITMENT_AGENCY = "recruitment_agency"
    GOV_TENDER_CONTRACTOR = "gov_tender_contractor"
    FMCG_DISTRIBUTOR = "fmcg_distributor"
    CUSTOM = "custom"


class VerticalPreset(BaseModel):
    """Preset configuration defining default ICP, signal triggers, sources, and budgets."""

    model_config = ConfigDict(from_attributes=True)

    id: VerticalPresetId
    name: str
    description: str
    category: LeadSourceCategory
    default_query: str
    icp_criteria: ICPCriteria
    intent_tags: list[str] = Field(default_factory=list)
    signal_triggers: list[str] = Field(default_factory=list)
    recommended_sources: list[str] = Field(default_factory=list)
    default_source_budgets: list[SourceBudget] = Field(default_factory=list)
    suggested_daily_budget_vnd: int = 500000
    min_fit_score: float = 60.0
    min_intent_score: float = 50.0


_VERTICAL_PRESETS: dict[VerticalPresetId, VerticalPreset] = {
    VerticalPresetId.B2B_SAAS: VerticalPreset(
        id=VerticalPresetId.B2B_SAAS,
        name="B2B SaaS & Tech Growth",
        description="Khách hàng B2B, công ty công nghệ đang tuyển lập trình viên, mở rộng hạ tầng và gọi vốn",
        category=LeadSourceCategory.JOB_MARKET,
        default_query="Tuyển dụng lập trình viên phần mềm IT doanh nghiệp",
        icp_criteria=ICPCriteria(
            target_industries=["Information Technology", "Software", "Fintech", "E-commerce"],
            target_locations=["Hà Nội", "Hồ Chí Minh", "Đà Nẵng"],
            target_company_sizes=["50-200", "200-500", "500+"],
            target_tech_stack=["React", "Node.js", "Python", "AWS", "Kubernetes", "PostgreSQL"],
            target_categories=[LeadSourceCategory.JOB_MARKET, LeadSourceCategory.ENTERPRISE],
            target_keywords=["developer", "engineer", "software", "tech", "chuyển đổi số", "saas"],
            negative_keywords=["gia công may mặc", "vận tải", "xây dựng"],
            min_fit_score=65.0,
        ),
        intent_tags=["hiring", "tech_stack", "expansion", "funding"],
        signal_triggers=["hiring", "tech_stack", "funding"],
        recommended_sources=["vn_jobs", "job_market", "vietnamworks", "enterprise"],
        default_source_budgets=[
            SourceBudget(source_name="vn_jobs", max_leads=50, priority=1),
            SourceBudget(source_name="job_market", max_leads=30, priority=2),
            SourceBudget(source_name="enterprise", max_leads=20, priority=3),
        ],
        suggested_daily_budget_vnd=500000,
        min_fit_score=65.0,
        min_intent_score=55.0,
    ),
    VerticalPresetId.REAL_ESTATE_INVESTOR: VerticalPreset(
        id=VerticalPresetId.REAL_ESTATE_INVESTOR,
        name="Bất Động Sản & Nhà Đầu Tư",
        description="Nhà đầu tư, môi giới F1, sàn giao dịch và người mua bán bất động sản cao cấp",
        category=LeadSourceCategory.REAL_ESTATE,
        default_query="Bất động sản nhà phố căn hộ chung cư cao cấp",
        icp_criteria=ICPCriteria(
            target_industries=["Real Estate", "Bất động sản", "Đầu tư tài chính"],
            target_locations=["Hà Nội", "Hồ Chí Minh", "Bình Dương", "Đà Nẵng", "Hải Phòng"],
            target_categories=[LeadSourceCategory.REAL_ESTATE, LeadSourceCategory.SOCIAL],
            target_keywords=[
                "biệt thự", "shophouse", "căn hộ cao cấp", "nhà mặt phố", "đất nền", "vinhome", "masterise"
            ],
            negative_keywords=["phòng trọ sinh viên", "ở ghép", "tìm người ở ghép"],
            min_fit_score=60.0,
        ),
        intent_tags=["real_estate", "bds", "investment"],
        signal_triggers=["real_estate", "property_listing"],
        recommended_sources=["batdongsan", "chotot", "muaban_bds", "social"],
        default_source_budgets=[
            SourceBudget(source_name="batdongsan", max_leads=50, priority=1),
            SourceBudget(source_name="chotot", max_leads=30, priority=2),
            SourceBudget(source_name="muaban_bds", max_leads=20, priority=3),
        ],
        suggested_daily_budget_vnd=600000,
        min_fit_score=60.0,
        min_intent_score=50.0,
    ),
    VerticalPresetId.RECRUITMENT_AGENCY: VerticalPreset(
        id=VerticalPresetId.RECRUITMENT_AGENCY,
        name="Headhunting & Tuyển Dụng Nhân Sự",
        description="Doanh nghiệp đang tuyển dụng số lượng lớn, HR Manager, Talent Acquisition cần dịch vụ săn đầu người",
        category=LeadSourceCategory.JOB_MARKET,
        default_query="Doanh nghiệp tuyển dụng nhân sự cấp cao quản lý",
        icp_criteria=ICPCriteria(
            target_industries=["Banking", "Finance", "Technology", "Manufacturing", "Retail"],
            target_locations=["Hà Nội", "Hồ Chí Minh"],
            target_categories=[LeadSourceCategory.JOB_MARKET, LeadSourceCategory.ENTERPRISE],
            target_keywords=["tuyển dụng", "hiring", "headcount", "manager", "director", "trưởng phòng"],
            negative_keywords=["thực tập sinh", "lao động phổ thông", "part-time"],
            min_fit_score=60.0,
        ),
        intent_tags=["hiring", "recruitment", "headhunting"],
        signal_triggers=["hiring", "expansion"],
        recommended_sources=["vietnamworks", "vn_jobs", "job_market", "enterprise"],
        default_source_budgets=[
            SourceBudget(source_name="vietnamworks", max_leads=40, priority=1),
            SourceBudget(source_name="vn_jobs", max_leads=40, priority=2),
            SourceBudget(source_name="enterprise", max_leads=20, priority=3),
        ],
        suggested_daily_budget_vnd=450000,
        min_fit_score=60.0,
        min_intent_score=50.0,
    ),
    VerticalPresetId.GOV_TENDER_CONTRACTOR: VerticalPreset(
        id=VerticalPresetId.GOV_TENDER_CONTRACTOR,
        name="Đấu Thầu & Mua Sắm Công",
        description="Nhà thầu, chủ đầu tư, ban quản lý dự án tham gia các gói thầu xây lắp, thiết bị y tế, CNTT",
        category=LeadSourceCategory.ENTERPRISE,
        default_query="Gói thầu mua sắm công thiết bị xây lắp CNTT",
        icp_criteria=ICPCriteria(
            target_industries=["Construction", "Medical Equipment", "Government", "IT Infrastructure"],
            target_locations=["Toàn quốc", "Hà Nội", "Hồ Chí Minh"],
            target_categories=[LeadSourceCategory.ENTERPRISE],
            target_keywords=["đấu thầu", "gói thầu", "muasamcong", "chủ đầu tư", "nhà thầu", "tbmt"],
            negative_keywords=["chợ đồ cũ", "thanh lý cá nhân"],
            min_fit_score=70.0,
        ),
        intent_tags=["tender", "procurement", "bidding"],
        signal_triggers=["tender", "procurement"],
        recommended_sources=["muasamcong", "enterprise"],
        default_source_budgets=[
            SourceBudget(source_name="muasamcong", max_leads=60, priority=1),
            SourceBudget(source_name="enterprise", max_leads=40, priority=2),
        ],
        suggested_daily_budget_vnd=700000,
        min_fit_score=70.0,
        min_intent_score=60.0,
    ),
    VerticalPresetId.FMCG_DISTRIBUTOR: VerticalPreset(
        id=VerticalPresetId.FMCG_DISTRIBUTOR,
        name="FMCG & Phân Phối Bán Lẻ",
        description="Đại lý phân phối, chuỗi cửa hàng bán lẻ, siêu thị mini và nhà nhập khẩu tiêu dùng nhanh",
        category=LeadSourceCategory.ENTERPRISE,
        default_query="Đại lý phân phối bán lẻ hàng tiêu dùng thực phẩm",
        icp_criteria=ICPCriteria(
            target_industries=["FMCG", "Retail", "Food & Beverage", "Distribution"],
            target_locations=["Hồ Chí Minh", "Hà Nội", "Cần Thơ", "Đà Nẵng"],
            target_categories=[LeadSourceCategory.ENTERPRISE, LeadSourceCategory.SOCIAL],
            target_keywords=["đại lý", "nhà phân phối", "tổng kho", "sỉ lẻ", "fmcg", "nhập khẩu"],
            negative_keywords=["bán lẻ 1 cái", "thanh lý tủ lạnh"],
            min_fit_score=55.0,
        ),
        intent_tags=["distribution", "wholesale", "fmcg"],
        signal_triggers=["business_registration", "expansion"],
        recommended_sources=["enterprise", "social", "telegram"],
        default_source_budgets=[
            SourceBudget(source_name="enterprise", max_leads=50, priority=1),
            SourceBudget(source_name="social", max_leads=30, priority=2),
            SourceBudget(source_name="telegram", max_leads=20, priority=3),
        ],
        suggested_daily_budget_vnd=400000,
        min_fit_score=55.0,
        min_intent_score=50.0,
    ),
    VerticalPresetId.CUSTOM: VerticalPreset(
        id=VerticalPresetId.CUSTOM,
        name="Tùy Chỉnh (Custom Campaign)",
        description="Tự do cấu hình tiêu chí ICP, bộ lọc ngành nghề, từ khóa và kênh thu thập dữ liệu",
        category=LeadSourceCategory.GENERAL,
        default_query="",
        icp_criteria=ICPCriteria(),
        intent_tags=[],
        signal_triggers=[],
        recommended_sources=["batdongsan", "chotot", "vn_jobs", "enterprise", "muasamcong", "social"],
        default_source_budgets=[],
        suggested_daily_budget_vnd=500000,
        min_fit_score=50.0,
        min_intent_score=50.0,
    ),
}


def list_vertical_presets() -> list[VerticalPreset]:
    """List all available vertical presets for Campaign Builder."""
    return list(_VERTICAL_PRESETS.values())


def get_vertical_preset(preset_id: str | VerticalPresetId) -> VerticalPreset:
    """Retrieve a vertical preset by identifier, fallback to CUSTOM if unknown."""
    if isinstance(preset_id, str):
        try:
            preset_enum = VerticalPresetId(preset_id.lower().strip())
        except ValueError:
            return _VERTICAL_PRESETS[VerticalPresetId.CUSTOM]
    else:
        preset_enum = preset_id

    return _VERTICAL_PRESETS.get(preset_enum, _VERTICAL_PRESETS[VerticalPresetId.CUSTOM])


def generate_reverse_icp(url: str, description: str = "") -> dict[str, Any]:
    """
    Reverse-ICP Analyzer: Infer target vertical, ICP criteria, keywords, and recommended
    sources based on a customer website URL or business profile prompt.
    """
    clean_url = (url or "").strip()
    parsed = urllib.parse.urlparse(clean_url if "://" in clean_url else f"https://{clean_url}")
    domain = (parsed.netloc or clean_url).lower().replace("www.", "")
    combined_text = f"{domain} {description}".lower()

    # Rule-based vertical classification heuristics
    if any(k in combined_text for k in ["bds", "batdongsan", "land", "realtor", "home", "vinhome", "property", "nha dat", "can ho"]):
        preset = get_vertical_preset(VerticalPresetId.REAL_ESTATE_INVESTOR)
        inferred_template = VerticalPresetId.REAL_ESTATE_INVESTOR
    elif any(k in combined_text for k in ["recruit", "headhunt", "tuyen dung", "hr", "talent", "staffing", "vieclam", "topcv", "job"]):
        preset = get_vertical_preset(VerticalPresetId.RECRUITMENT_AGENCY)
        inferred_template = VerticalPresetId.RECRUITMENT_AGENCY
    elif any(k in combined_text for k in ["thau", "tender", "dauthau", "bidding", "muasamcong", "xay dung", "du an cong"]):
        preset = get_vertical_preset(VerticalPresetId.GOV_TENDER_CONTRACTOR)
        inferred_template = VerticalPresetId.GOV_TENDER_CONTRACTOR
    elif any(k in combined_text for k in ["fmcg", "phan phoi", "dai ly", "food", "beverage", "consumer", "tap hoa", "sieu thi"]):
        preset = get_vertical_preset(VerticalPresetId.FMCG_DISTRIBUTOR)
        inferred_template = VerticalPresetId.FMCG_DISTRIBUTOR
    elif any(k in combined_text for k in ["saas", "software", "tech", "cloud", "api", "ai", "platform", "app", "phan mem"]):
        preset = get_vertical_preset(VerticalPresetId.B2B_SAAS)
        inferred_template = VerticalPresetId.B2B_SAAS
    else:
        preset = get_vertical_preset(VerticalPresetId.B2B_SAAS)
        inferred_template = VerticalPresetId.B2B_SAAS

    extracted_keywords = list(preset.icp_criteria.target_keywords)
    # Add domain token as a specific keyword if meaningful
    domain_token = re.sub(r"\.(com|vn|net|io|org|co|com\.vn)$", "", domain)
    if len(domain_token) > 2 and domain_token not in extracted_keywords:
        extracted_keywords.insert(0, domain_token)

    return {
        "analyzed_domain": domain,
        "suggested_template": inferred_template.value,
        "preset_name": preset.name,
        "category": preset.category.value,
        "icp_criteria": {
            "target_industries": preset.icp_criteria.target_industries,
            "target_locations": preset.icp_criteria.target_locations,
            "target_keywords": extracted_keywords,
            "negative_keywords": preset.icp_criteria.negative_keywords,
            "target_categories": [c.value for c in preset.icp_criteria.target_categories],
            "min_fit_score": preset.min_fit_score,
        },
        "intent_tags": preset.intent_tags,
        "signal_triggers": preset.signal_triggers,
        "recommended_sources": preset.recommended_sources,
        "suggested_query": preset.default_query,
        "suggested_daily_budget_vnd": preset.suggested_daily_budget_vnd,
    }
