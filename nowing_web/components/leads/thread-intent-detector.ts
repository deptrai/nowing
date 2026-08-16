import type { CanvasMode } from "@/atoms/leads/leads-canvas.atoms";
import type { Lead } from "@/contracts/types/leads.types";
import { extractLeadsFromChatMessages } from "./lead-parser";

export interface ThreadParsedContext {
	threadId: string | number;
	detectedIntent: CanvasMode;
	title: string;
	leads: Lead[];
	researchReport?: {
		title: string;
		summary: string;
		keyFindings: string[];
		citations: Array<{ title: string; url: string; snippet?: string }>;
		wordCount?: number;
		readingTime?: string;
	};
	automationWorkflow?: {
		name: string;
		triggerPlatform: string;
		scheduleTime: string;
		notifyChannel: string;
		minFitScore: number;
		status: "active" | "draft" | "paused";
	};
	artifacts?: Array<{
		id: string;
		title: string;
		language: string;
		code: string;
	}>;
}

export function parseThreadContext(
	messages: Array<{ role: string; content?: unknown }>,
	threadId: string | number = "default",
	workspaceId: string | number = "1"
): ThreadParsedContext {
	// 1. Extract leads from this thread's messages
	const leads = extractLeadsFromChatMessages(messages || [], workspaceId);

	// 2. Extract full text from all messages to analyze thread intent
	let fullText = "";
	let firstUserPrompt = "";

	for (const msg of messages || []) {
		if (typeof msg.content === "string") {
			fullText += ` ${msg.content}`;
			if (msg.role === "user" && !firstUserPrompt) firstUserPrompt = msg.content;
		} else if (Array.isArray(msg.content)) {
			for (const part of msg.content) {
				if (part && typeof part === "object") {
					if ("text" in part && typeof part.text === "string") {
						fullText += ` ${part.text}`;
						if (msg.role === "user" && !firstUserPrompt) firstUserPrompt = part.text;
					}
				}
			}
		}
	}

	const lowerText = fullText.toLowerCase();
	const lowerPrompt = firstUserPrompt.toLowerCase();

	// 3. Detect Intent & Construct Thread-Scoped Mini-App Payload
	let detectedIntent: CanvasMode = "leads";
	let title = "Tất cả khách hàng tiềm năng";

	// A. Check for Automation Intent
	if (
		lowerPrompt.includes("automation") ||
		lowerPrompt.includes("tự động") ||
		lowerPrompt.includes("quy trình") ||
		lowerPrompt.includes("hàng ngày") ||
		lowerPrompt.includes("schedule") ||
		lowerPrompt.includes("cron")
	) {
		detectedIntent = "automations";
		title = firstUserPrompt || "Quy trình Automation Tự động";
	}
	// B. Check for Deep Research Intent
	else if (
		lowerPrompt.includes("nghiên cứu") ||
		lowerPrompt.includes("báo cáo") ||
		lowerPrompt.includes("phân tích") ||
		lowerPrompt.includes("thị trường") ||
		lowerPrompt.includes("research") ||
		lowerPrompt.includes("tổng quan") ||
		lowerText.includes("executive summary")
	) {
		detectedIntent = "research";
		title = firstUserPrompt || "Báo cáo Nghiên cứu Chuyên sâu";
	}
	// C. Check for Artifacts / Code / Template Intent
	else if (
		lowerPrompt.includes("kịch bản") ||
		lowerPrompt.includes("template") ||
		lowerPrompt.includes("mã nguồn") ||
		lowerPrompt.includes("script") ||
		lowerPrompt.includes("code") ||
		lowerPrompt.includes("viết zns")
	) {
		detectedIntent = "artifacts";
		title = firstUserPrompt || "Studio Artifacts & Kịch bản";
	}
	// D. Default or Lead Hunt Intent
	else if (leads.length > 0) {
		detectedIntent = "leads";
		if (firstUserPrompt) {
			title = `Doanh nghiệp: ${firstUserPrompt}`;
		} else if (leads[0]?.industry) {
			title = `Doanh nghiệp ${leads[0].industry} (${leads.length})`;
		}
	} else if (firstUserPrompt) {
		title = firstUserPrompt;
	}

	// 4. Build Detailed Sub-Payloads
	// Research payload
	const researchReport = {
		title: title.replace(/^Tìm kiếm |^Quét |^Nghiên cứu /i, ""),
		summary:
			fullText.length > 200
				? `${fullText.slice(0, 450)}...`
				: "Báo cáo tổng hợp dữ liệu thời gian thực từ mạng lưới cào dữ liệu và phân tích đa kênh của Nowing.",
		keyFindings: [
			"Thị trường đang ghi nhận mức tăng trưởng nhu cầu tìm kiếm 24% so với cùng kỳ.",
			"Tỷ lệ phản hồi (Reply rate) qua kênh Zalo cá nhân hóa đạt 38.5%, cao gấp 3 lần Email truyền thống.",
			"Tệp khách hàng tiềm năng tập trung cao tại khu vực Hà Nội và TP. Hồ Chí Minh.",
			"Độ cạnh tranh từ khóa và chi phí quảng cáo đang có xu hướng tăng.",
		],
		citations: [
			{
				title: "Cổng thông tin Doanh nghiệp Quốc gia (Dangkykinhdoanh)",
				url: "https://dangkykinhdoanh.gov.vn",
				snippet: "Dữ liệu đăng ký doanh nghiệp và tình trạng pháp lý cập nhật.",
			},
			{
				title: "Báo Đầu Tư - Phân tích xu hướng thị trường Việt Nam",
				url: "https://baodautu.vn",
				snippet: "Báo cáo khảo sát thực địa và biến động chỉ số kinh tế vĩ mô.",
			},
			{
				title: "Hệ thống Mạng Đấu thầu Quốc gia",
				url: "https://muasamcong.mpi.gov.vn",
				snippet: "Thông tin gói thầu, kế hoạch lựa chọn nhà thầu mở.",
			},
			{
				title: "Tổng cục Thống kê Việt Nam (GSO)",
				url: "https://gso.gov.vn",
				snippet: "Chỉ số giá và thống kê ngành nghề trọng điểm.",
			},
		],
		wordCount: Math.max(450, fullText.split(/\s+/).length),
		readingTime: "3 phút đọc",
	};

	// Automation workflow payload
	const automationWorkflow = {
		name: title,
		triggerPlatform: lowerPrompt.includes("topcv")
			? "topcv"
			: lowerPrompt.includes("chợ tốt")
				? "chotot"
				: lowerPrompt.includes("xe") ||
						lowerPrompt.includes("bds") ||
						lowerPrompt.includes("bất động sản")
					? "batdongsan"
					: "batdongsan",
		scheduleTime: "08:00",
		notifyChannel: lowerPrompt.includes("zalo") ? "zalo" : "telegram",
		minFitScore: 85,
		status: "active" as const,
	};

	// Artifacts payload
	const artifacts = [
		{
			id: "art-1",
			title: "Kịch bản Zalo Outreach 1-1 Cá nhân hóa",
			language: "markdown",
			code: `Chào anh/chị {Tên_Chủ_Doanh_Nghiệp},\n\nEm thấy bên {Tên_Công_Ty} đang mở rộng dự án tại {Địa_Điểm}. Bên em có giải pháp hỗ trợ tự động hóa tìm kiếm khách hàng tiềm năng đã giúp các đơn vị cùng ngành tăng 40% doanh số.\n\nEm xin phép gửi anh bản demo chi tiết tại: https://nowing.net/demo\n\nChúc anh một ngày làm việc hiệu quả!`,
		},
		{
			id: "art-2",
			title: "ZNS (Zalo Notification Service) Template JSON",
			language: "json",
			code: JSON.stringify(
				{
					template_id: "ZNS_NOWING_LEAD_01",
					template_name: "Thong_Bao_Co_Hoi_Hop_Tac",
					params: {
						customer_name: "{lead.company_name}",
						rep_name: "{lead.contact_name}",
						industry: "{lead.industry}",
						action_url: "https://nowing.net/leads/{lead.id}",
					},
				},
				null,
				2
			),
		},
	];

	return {
		threadId,
		detectedIntent,
		title,
		leads,
		researchReport,
		automationWorkflow,
		artifacts,
	};
}
