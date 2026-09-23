// Static presets and source catalog for the campaign builder.

import type { CampaignIntent, IcpVerticalTemplate } from "@/contracts/types/campaign.types";

export const VERTICAL_PRESETS: Record<
	IcpVerticalTemplate,
	{
		label: string;
		description: string;
		industries: string[];
		locations: string[];
		companySize: string;
		techStack: string[];
		intents: CampaignIntent[];
		sources: string[];
	}
> = {
	b2b_saas: {
		label: "B2B SaaS / Chuyển Đổi Số",
		description: "Tìm các doanh nghiệp đang tuyển IT, nâng cấp phần mềm, công nghệ cao",
		industries: ["Công nghệ thông tin", "Phần mềm", "Fintech", "E-commerce"],
		locations: ["Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng"],
		companySize: "50-200 nhân sự",
		techStack: ["React", "Node.js", "AWS", "Docker", "PostgreSQL"],
		intents: ["MUA", "TUYỂN", "HỢP TÁC"],
		sources: ["topcv", "facebook", "telegram", "linkedin"],
	},
	real_estate_investor: {
		label: "Bất Động Sản & Nhà Đầu Tư",
		description: "Chủ đầu tư, sàn môi giới, người đăng tin bán/thuê BĐS giá trị cao",
		industries: ["Bất động sản", "Xây dựng", "Đầu tư tài chính"],
		locations: ["TP. Hồ Chí Minh", "Bình Dương", "Đồng Nai", "Hà Nội"],
		companySize: "10-50 nhân sự",
		techStack: [],
		intents: ["BÁN", "MUA"],
		sources: ["batdongsan", "facebook", "telegram"],
	},
	recruitment_agency: {
		label: "Headhunter & Dịch Vụ Tuyển Dụng",
		description: "Các công ty đang đăng tuyển dụng ồ ạt, tăng trưởng nóng headcount",
		industries: ["Bán lẻ", "F&B", "Sản xuất", "Công nghệ"],
		locations: ["Toàn quốc", "Hà Nội", "TP. Hồ Chí Minh"],
		companySize: "100-500 nhân sự",
		techStack: [],
		intents: ["TUYỂN"],
		sources: ["topcv", "facebook", "linkedin"],
	},
	gov_tender_contractor: {
		label: "Nhà Thầu & Đấu Thầu Công",
		description: "Doanh nghiệp thường xuyên trúng thầu hoặc đang mời thầu công khai",
		industries: ["Xây dựng", "Y tế", "Thiết bị giáo dục", "Hạ tầng"],
		locations: ["Hà Nội", "Đà Nẵng", "TP. Hồ Chí Minh", "Cần Thơ"],
		companySize: "50-500 nhân sự",
		techStack: [],
		intents: ["ĐẤU THẦU", "BÁN"],
		sources: ["tender"],
	},
	fmcg_distributor: {
		label: "Phân Phối & Đại Lý FMCG",
		description: "Các nhà phân phối, đại lý sỉ tìm kiếm nguồn hàng hoặc mở rộng kênh",
		industries: ["Hàng tiêu dùng nhanh (FMCG)", "Thực phẩm", "Mỹ phẩm"],
		locations: ["Miền Bắc", "Miền Nam", "Miền Trung"],
		companySize: "20-100 nhân sự",
		techStack: [],
		intents: ["BÁN", "MUA", "HỢP TÁC"],
		sources: ["facebook", "telegram"],
	},
	custom: {
		label: "Tùy chỉnh riêng (Custom ICP)",
		description: "Thiết lập tiêu chí khách hàng mục tiêu từ đầu hoặc qua Reverse ICP",
		industries: [],
		locations: [],
		companySize: "1-50 nhân sự",
		techStack: [],
		intents: ["BÁN"],
		sources: ["facebook", "telegram", "batdongsan", "topcv", "tender"],
	},
};

export const AVAILABLE_SOURCES = [
	{
		id: "facebook",
		name: "Facebook Groups",
		icon: "👥",
		description: "Hội nhóm kinh doanh, tìm đối tác, rao vặt B2B",
	},
	{
		id: "telegram",
		name: "Telegram Channels",
		icon: "✈️",
		description: "Kênh deal sỉ, nguồn hàng, tín hiệu đầu tư kín",
	},
	{
		id: "batdongsan",
		name: "Batdongsan.com.vn",
		icon: "🏠",
		description: "Tin đăng chính chủ & môi giới BĐS toàn quốc",
	},
	{
		id: "topcv",
		name: "TopCV & ITviec",
		icon: "💼",
		description: "Tín hiệu tuyển dụng, mở rộng quy mô phòng ban",
	},
	{
		id: "tender",
		name: "Mua Sắm Công (Tenders)",
		icon: "🏛️",
		description: "Hồ sơ mời thầu, gói thầu nhà nước & tập đoàn",
	},
];
