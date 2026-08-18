import type { Lead } from "@/contracts/types/leads.types";

const COMPANY_KEYWORD_REGEX =
	/(?:Công ty|Tập đoàn|Doanh nghiệp|Văn phòng|TNHH|JSC|Corp|Group|Land|BĐS|Real Estate|Bank|Capital|Agency|Studio|Store|Shop|Clinic|Hospital|Hotel|Resort|Restaurant|Quỹ|Ban Quản lý|Viện|Trường|Chi nhánh|Đại lý|Nhà phân phối|HANDICO|Vingroup|Sun Group|Novaland|SGG Homes|Highlands|PropTech)/i;

function cleanMarkdownValue(str: string | null | undefined): string {
	if (!str) return "";
	return str
		.replace(/\*\*/g, "")
		.replace(/\*/g, "")
		.replace(/\[(.*?)\]\(.*?\)/g, "$1") // markdown links -> label
		.replace(/\[.*?\]|\(.*?\)/g, "")
		.replace(/Source/gi, "")
		.replace(/\|/g, "")
		.trim();
}

function extractPhoneOnly(str: string | null | undefined): string | null {
	if (!str) return null;
	const cleaned = cleanMarkdownValue(str);
	// Search for Vietnamese mobile or landline pattern
	const match = cleaned.match(/(?:(?:\+84|84|0)[1-9][0-9]{7,9})/);
	if (match) {
		return match[0].startsWith("84") ? `0${match[0].slice(2)}` : match[0];
	}
	// Fallback check if digits only with length 9-11
	const digits = cleaned.replace(/\D/g, "");
	if (digits.length >= 9 && digits.length <= 11) {
		return digits.startsWith("84") ? `0${digits.slice(2)}` : digits;
	}
	return null;
}

function extractDomainOnly(str: string | null | undefined, companyFallback: string): string {
	if (str) {
		const cleaned = cleanMarkdownValue(str)
			.replace(/^https?:\/\//i, "")
			.replace(/\/.*$/, "")
			.replace(/[^\w.-]/g, "")
			.toLowerCase();
		if (cleaned.includes(".") && cleaned.length >= 4) {
			return cleaned;
		}
	}
	const slug = companyFallback
		.toLowerCase()
		.normalize("NFD")
		.replace(/[\u0300-\u036f]/g, "")
		.replace(/[^a-z0-9]/g, "");
	return slug ? `${slug.slice(0, 20)}.vn` : "nowing.vn";
}

/**
 * Parses markdown tables into structured Lead items.
 */
function parseMarkdownTables(text: string, wsId: number): Lead[] {
	const tableLeads: Lead[] = [];
	const lines = text.split("\n");

	let inTable = false;
	let headers: string[] = [];
	let colMap = {
		name: -1,
		phone: -1,
		website: -1,
		location: -1,
		industry: -1,
		desc: -1,
	};

	for (const rawLine of lines) {
		const line = rawLine.trim();

		// Table row starts and ends with pipe
		if (line.startsWith("|") && line.endsWith("|")) {
			const cells = line
				.slice(1, -1)
				.split("|")
				.map((c) => c.trim());

			// Skip separator row (|---|---|)
			if (cells.every((c) => /^[-:\s]+$/.test(c))) {
				inTable = true;
				continue;
			}

			if (!inTable) {
				// This is header row
				headers = cells.map((c) => c.toLowerCase());
				colMap = {
					name: headers.findIndex((h) =>
						/(?:tên|doanh nghiệp|công ty|khách hàng|đơn vị|môi giới|name|company|title|tiêu đề)/i.test(
							h
						)
					),
					phone: headers.findIndex((h) =>
						/(?:sđt|hotline|điện thoại|phone|tel|liên hệ|mobile)/i.test(h)
					),
					website: headers.findIndex((h) => /(?:website|web|domain|link|trang web)/i.test(h)),
					location: headers.findIndex((h) =>
						/(?:địa chỉ|khu vực|location|address|quận|thành phố|trụ sở)/i.test(h)
					),
					industry: headers.findIndex((h) => /(?:ngành|lĩnh vực|industry|phân khúc)/i.test(h)),
					desc: headers.findIndex((h) =>
						/(?:ghi chú|mô tả|đánh giá|dự án|description|note|rating)/i.test(h)
					),
				};

				// Fallback if name column not explicitly named
				if (colMap.name === -1 && cells.length >= 2) {
					// Usually 2nd column after # / STT
					colMap.name = headers.findIndex((h) => /(?:#|stt|no)/i.test(h)) === 0 ? 1 : 0;
				}
				continue;
			}

			// Parse data row
			if (inTable && cells.length >= 2) {
				const rawName = colMap.name >= 0 ? cells[colMap.name] : cells[0];
				const companyName = cleanMarkdownValue(rawName);

				// Skip if empty or header-like text
				if (!companyName || companyName.length < 2 || companyName.length > 90) continue;
				if (
					/^(tên doanh nghiệp|công ty|tên|doanh nghiệp|stt|#|stt\.|no\.|hạng mục)/i.test(
						companyName
					)
				) {
					continue;
				}

				const rawPhone = colMap.phone >= 0 ? cells[colMap.phone] : null;
				const rawWebsite = colMap.website >= 0 ? cells[colMap.website] : null;
				const rawLocation = colMap.location >= 0 ? cells[colMap.location] : null;
				const rawIndustry = colMap.industry >= 0 ? cells[colMap.industry] : null;
				const rawDesc = colMap.desc >= 0 ? cells[colMap.desc] : null;

				const cleanPhone = extractPhoneOnly(rawPhone);
				const domain = extractDomainOnly(rawWebsite, companyName);
				const location = cleanMarkdownValue(rawLocation) || "Hà Nội, Việt Nam";
				const industry = cleanMarkdownValue(rawIndustry) || "Bất động sản";
				const snippet = cleanMarkdownValue(rawDesc) || "Tìm thấy qua AI Scraper";

				const leadIndex = tableLeads.length;
				const fakeUuid = `00000000-0000-4000-8000-${String(leadIndex + 1).padStart(12, "0")}`;

				tableLeads.push({
					id: fakeUuid,
					workspace_id: wsId,
					company_name: companyName,
					domain,
					source: "chat_scraper",
					source_url: domain ? `https://${domain}` : null,
					industry,
					location,
					phone: cleanPhone,
					fit_score: 96 - leadIndex * 2,
					intent_score: 92 - leadIndex * 2,
					composite_score: 94 - leadIndex * 2,
					status: "new",
					intent: "BÁN",
					content_snippet: snippet,
					tech_stack: [],
					enriched: true,
					is_unlocked: false,
					version: 1,
					created_at: new Date().toISOString(),
				});
			}
		} else {
			// End of table block
			inTable = false;
		}
	}

	return tableLeads;
}

/**
 * Intelligent lead parser that extracts structured company/lead listings
 * from chat assistant messages or tool execution outputs.
 */
export function parseLeadsFromText(text: string, workspaceId: number | string = 1): Lead[] {
	if (!text || typeof text !== "string") return [];

	const wsId =
		typeof workspaceId === "number" ? workspaceId : Number.parseInt(String(workspaceId), 10) || 1;

	// 1. Try extracting structured Markdown tables first
	const tableLeads = parseMarkdownTables(text, wsId);
	if (tableLeads.length > 0) {
		return tableLeads;
	}

	// 2. Fallback to list/bullet extraction
	const leads: Lead[] = [];
	const blocks = text.split(/(?=\n\s*(?:\d+[.)]|#{1,4}\s+|[-*•]\s*\*\*|\*\*\d+[.)]))/);

	for (const block of blocks) {
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
			/^(Dưới đây|Sau đây|Tổng quan|Danh sách|Báo cáo|Tóm tắt|Lưu ý|Gợi ý|Kết quả|Bảng)/i.test(
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

		const cleanCompany = cleanMarkdownValue(rawCompanyName);
		const cleanPhone = extractPhoneOnly(phoneMatch ? phoneMatch[1] : null);
		const domain = extractDomainOnly(websiteMatch ? websiteMatch[1] : null, cleanCompany);
		const cleanLocation =
			cleanMarkdownValue(locationMatch ? locationMatch[1] : null) || "Hà Nội, Việt Nam";
		const cleanIndustry =
			cleanMarkdownValue(industryMatch ? industryMatch[1] : null) || "Bất động sản";
		const cleanSnippet =
			cleanMarkdownValue(descMatch ? descMatch[1] : null) || "Tìm thấy qua AI Scraper";

		const leadIndex = leads.length;
		const fakeUuid = `00000000-0000-4000-8000-${String(leadIndex + 1).padStart(12, "0")}`;

		leads.push({
			id: fakeUuid,
			workspace_id: wsId,
			company_name: cleanCompany,
			domain,
			source: "chat_scraper",
			source_url: domain ? `https://${domain}` : null,
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
			is_unlocked: false,
			is_new_from_zero: false,
			version: 1,
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
