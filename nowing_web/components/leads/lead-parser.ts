import type { Lead } from "@/contracts/types/leads.types";

/**
 * Intelligent lead parser that extracts structured company/lead listings
 * from chat assistant messages or tool execution outputs.
 */
export function parseLeadsFromText(
	text: string,
	workspaceId: number | string = 1
): Lead[] {
	if (!text || typeof text !== "string") return [];

	const leads: Lead[] = [];
	const wsId = typeof workspaceId === "number" ? workspaceId : Number.parseInt(String(workspaceId), 10) || 1;

	// Pattern 1: Numbered list items (e.g. 1. **Công ty ABC** or 1. Cong ty ABC)
	const numberedBlocks = text.split(/(?=\n\s*\d+[\.\)]\s+)/);

	const COMPANY_KEYWORD_REGEX =
		/(?:Công ty|Tập đoàn|Doanh nghiệp|Văn phòng|TNHH|JSC|Corp|Group|Land|BĐS|Real Estate|Bank|Capital|Agency|Studio|Store|Shop|Clinic|Hospital|Hotel|Resort|Restaurant|Quỹ|Ban Quản lý|Viện|Trường|Chi nhánh|Đại lý|Nhà phân phối)/i;

	for (const block of numberedBlocks) {
		const headerMatch = block.match(/^\s*\d+[\.\)]\s+\**([^*\n]+)\**/);
		if (!headerMatch) continue;

		const rawCompanyName = headerMatch[1].trim().replace(/^[-–—:]\s*/, "");
		if (rawCompanyName.length < 3 || rawCompanyName.length > 80) continue;

		// Extract fields from lines within the block
		const locationMatch = block.match(/(?:Địa chỉ|Location|Địa điểm|Khu vực)[:\s]+([^\n\r]+)/i);
		const phoneMatch = block.match(/(?:Điện thoại|Phone|SĐT|Tel|Hotline)[:\s]+([^\n\r]+)/i);
		const websiteMatch = block.match(/(?:Website|Web|Trang web|Link)[:\s]+([^\s\n\r]+)/i);
		const industryMatch = block.match(/(?:Ngành|Industry|Lĩnh vực)[:\s]+([^\n\r]+)/i);
		const descMatch = block.match(/(?:Mô tả|Description|Hoạt động|Đánh giá)[:\s]+([^\n\r]+)/i);

		const isCompanyLike =
			COMPANY_KEYWORD_REGEX.test(rawCompanyName) ||
			Boolean(phoneMatch) ||
			Boolean(websiteMatch) ||
			Boolean(locationMatch);

		if (!isCompanyLike) continue;

		const stripMd = (str: string | null | undefined) =>
			str ? str.replace(/\*\*/g, "").replace(/\[.*?\]|\(.*?\)|Source/gi, "").trim() : null;

		let cleanPhone = stripMd(phoneMatch ? phoneMatch[1] : null);
		let cleanWebsite = stripMd(websiteMatch ? websiteMatch[1] : null);
		const cleanLocation = stripMd(locationMatch ? locationMatch[1] : null) || "Hà Nội, Việt Nam";
		const cleanIndustry = stripMd(industryMatch ? industryMatch[1] : null) || "Bất động sản";
		const cleanSnippet = stripMd(descMatch ? descMatch[1] : null) || "Tìm thấy qua AI Scraper";

		// Clean up website / domain
		if (cleanWebsite) {
			cleanWebsite = cleanWebsite.replace(/^https?:\/\//i, "").replace(/\/.*$/, "");
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

	// Iterate from newest message to oldest
	for (let i = messages.length - 1; i >= 0; i--) {
		const msg = messages[i];
		if (!msg || msg.role !== "assistant") continue;

		let text = "";
		if (typeof msg.content === "string") {
			text = msg.content;
		} else if (Array.isArray(msg.content)) {
			text = msg.content
				.map((part) => {
					if (typeof part === "string") return part;
					if (part && typeof part === "object" && "text" in part) return (part as { text: string }).text;
					return "";
				})
				.join("\n");
		}

		if (!text) continue;

		const parsed = parseLeadsFromText(text, workspaceId);
		for (const lead of parsed) {
			const normalizedName = lead.company_name.toLowerCase().trim();
			if (!seenNames.has(normalizedName)) {
				seenNames.add(normalizedName);
				allLeads.push(lead);
			}
		}

		// If we already found leads in the latest message, stop
		if (allLeads.length > 0) {
			break;
		}
	}

	return allLeads;
}
