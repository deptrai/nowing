import type { Lead } from "@/contracts/types/leads.types";

/**
 * Intelligent lead parser that extracts structured company/lead listings
 * from chat assistant messages or tool execution outputs.
 */
export function parseLeadsFromText(text: string, workspaceId: number | string = 1): Lead[] {
	if (!text || typeof text !== "string") return [];

	const leads: Lead[] = [];
	const wsId =
		typeof workspaceId === "number" ? workspaceId : Number.parseInt(String(workspaceId), 10) || 1;

	// Split by numbered list items, markdown headers, or bold lines
	const blocks = text.split(/(?=\n\s*(?:\d+[.)]|#{1,4}\s+|[-*•]\s*\*\*|\*\*\d+[.)]))/);

	const COMPANY_KEYWORD_REGEX =
		/(?:Công ty|Tập đoàn|Doanh nghiệp|Văn phòng|TNHH|JSC|Corp|Group|Land|BĐS|Real Estate|Bank|Capital|Agency|Studio|Store|Shop|Clinic|Hospital|Hotel|Resort|Restaurant|Quỹ|Ban Quản lý|Viện|Trường|Chi nhánh|Đại lý|Nhà phân phối|HANDICO|Vingroup|Sun Group|Novaland|SGG Homes|Highlands|PropTech)/i;

	for (const block of blocks) {
		// Match numbered or bold or header title
		let rawCompanyName: string | null = null;

		const numMatch = block.match(/^\s*(?:\d+[.)]|#{1,4})\s*\**([^*\n\r]+)\**/);
		const boldMatch = block.match(/^\s*[-*•]?\s*\*\*([^*\n\r]+)\*\*/);
		const plainHeaderMatch = block.match(/^\s*([A-ZÀ-Ỹ0-9][A-Za-zÀ-ỹ0-9\s&.–—()-]{4,70})(?=\n|$)/);

		if (numMatch) {
			rawCompanyName = numMatch[1].trim().replace(/^[-–—:]\s*/, "");
		} else if (boldMatch) {
			rawCompanyName = boldMatch[1].trim().replace(/^[-–—:]\s*/, "");
		} else if (plainHeaderMatch && COMPANY_KEYWORD_REGEX.test(plainHeaderMatch[1])) {
			rawCompanyName = plainHeaderMatch[1].trim();
		}

		if (!rawCompanyName || rawCompanyName.length < 3 || rawCompanyName.length > 80) {
			continue;
		}

		// Filter out non-company headers (like "Tóm tắt điều hành", "Dưới đây là danh sách")
		if (
			/^(Dưới đây|Sau đây|Tổng quan|Danh sách|Báo cáo|Tóm tắt|Lưu ý|Gợi ý|Kết quả)/i.test(
				rawCompanyName
			)
		) {
			continue;
		}

		// Extract fields from lines within the block
		const locationMatch = block.match(
			/(?:Địa chỉ|Location|Địa điểm|Khu vực|Trụ sở|Trụ sở chính)[:\s]+([^\n\r]+)/i
		);
		const phoneMatch = block.match(/(?:Điện thoại|Phone|SĐT|Tel|Hotline)[:\s]+([^\n\r]+)/i);
		const websiteMatch = block.match(/(?:Website|Web|Trang web|Link)[:\s]+([^\s\n\r]+)/i);
		const industryMatch = block.match(
			/(?:Ngành|Industry|Lĩnh vực|Lĩnh vực \/ Dự án)[:\s]+([^\n\r]+)/i
		);
		const descMatch = block.match(
			/(?:Mô tả|Description|Hoạt động|Đánh giá|Dự án nổi bật)[:\s]+([^\n\r]+)/i
		);

		const isCompanyLike =
			COMPANY_KEYWORD_REGEX.test(rawCompanyName) ||
			Boolean(phoneMatch) ||
			Boolean(websiteMatch) ||
			Boolean(locationMatch) ||
			Boolean(industryMatch);

		if (!isCompanyLike) continue;

		const stripMd = (str: string | null | undefined) =>
			str
				? str
						.replace(/\*\*/g, "")
						.replace(/\[.*?\]|\(.*?\)|Source/gi, "")
						.trim()
				: null;

		let cleanPhone = stripMd(phoneMatch ? phoneMatch[1] : null);
		let cleanWebsite = stripMd(websiteMatch ? websiteMatch[1] : null);
		const cleanLocation = stripMd(locationMatch ? locationMatch[1] : null) || "Hà Nội, Việt Nam";
		const cleanIndustry = stripMd(industryMatch ? industryMatch[1] : null) || "Bất động sản";
		const cleanSnippet = stripMd(descMatch ? descMatch[1] : null) || "Tìm thấy qua AI Scraper";

		// Clean up website / domain
		if (cleanWebsite) {
			cleanWebsite = cleanWebsite
				.replace(/^https?:\/\//i, "")
				.replace(/\/.*$/, "")
				.replace(/[^\w.-]/g, "");
		}

		// Ensure phone format
		if (cleanPhone && cleanPhone.length < 6) {
			cleanPhone = null;
		}

		// Deterministic UUID for lead
		const leadIndex = leads.length;
		const fakeUuid = `00000000-0000-4000-8000-${String(leadIndex + 1).padStart(12, "0")}`;

		leads.push({
			id: fakeUuid,
			workspace_id: wsId,
			company_name: rawCompanyName,
			domain: cleanWebsite || `${rawCompanyName.toLowerCase().replace(/[^a-z0-9]/g, "")}.vn`,
			source: "chat_scraper",
			source_url: cleanWebsite ? `https://${cleanWebsite}` : null,
			industry: cleanIndustry,
			location: cleanLocation,
			phone: cleanPhone,
			fit_score: 95 - leadIndex * 3,
			intent_score: 90 - leadIndex * 2,
			composite_score: 93 - leadIndex * 2,
			status: "new",
			intent: "BÁN",
			content_snippet: cleanSnippet,
			tech_stack: [],
			enriched: true,
			created_at: new Date().toISOString(),
		});
	}

	return leads;
}

/**
 * Extracts leads from all assistant messages in the chat history.
 */
export function extractLeadsFromChatMessages(
	messages: Array<{ role: string; content?: unknown }>,
	workspaceId: number | string = 1
): Lead[] {
	if (!messages || !Array.isArray(messages)) return [];

	const allLeads: Lead[] = [];
	const seenNames = new Set<string>();

	// Iterate across all messages in order
	for (const msg of messages) {
		let text = "";
		if (typeof msg.content === "string") {
			text = msg.content;
		} else if (Array.isArray(msg.content)) {
			text = msg.content
				.map((part) => {
					if (typeof part === "string") return part;
					if (part && typeof part === "object" && "text" in part) {
						return (part as { text: string }).text;
					}
					return "";
				})
				.join("\n");
		}

		if (!text) continue;

		const extracted = parseLeadsFromText(text, workspaceId);
		for (const lead of extracted) {
			const normalizedName = lead.company_name.toLowerCase().replace(/[^a-z0-9]/g, "");
			if (!seenNames.has(normalizedName)) {
				seenNames.add(normalizedName);
				allLeads.push(lead);
			}
		}
	}

	return allLeads;
}
