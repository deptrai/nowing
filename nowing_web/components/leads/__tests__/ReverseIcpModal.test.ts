import assert from "node:assert/strict";
import { test } from "node:test";

// Type definitions to be implemented in contracts/types/leads.types.ts
interface FilterPresets {
	platforms: string[];
	intent: string;
	target_industries: string[];
	locations: string[];
	company_size_range?: string | null;
}

// ---------------------------------------------------------------------------
// 1. URL Normalization Helper Tests (Frontend Preflight)
// ---------------------------------------------------------------------------
function cleanUrlInput(raw: string): string {
	const trimmed = raw.trim();
	if (!trimmed) return "";
	if (!/^https?:\/\//i.test(trimmed)) {
		return `https://${trimmed}`;
	}
	return trimmed;
}

test("cleanUrlInput prepends https:// if missing", () => {
	assert.equal(cleanUrlInput("vinhomes.vn"), "https://vinhomes.vn");
	assert.equal(cleanUrlInput("topcv.vn/vieclam"), "https://topcv.vn/vieclam");
	assert.equal(cleanUrlInput("https://haravan.com"), "https://haravan.com");
	assert.equal(cleanUrlInput("http://base.vn"), "http://base.vn");
});

test("cleanUrlInput handles empty or whitespace input", () => {
	assert.equal(cleanUrlInput(""), "");
	assert.equal(cleanUrlInput("   "), "");
});

// ---------------------------------------------------------------------------
// 2. Sample Domain Selection & Persona Selection Tests
// ---------------------------------------------------------------------------
const SAMPLE_DOMAINS = [
	{ label: "Vinhomes (BĐS)", url: "vinhomes.vn" },
	{ label: "TopCV (Tuyển dụng)", url: "topcv.vn" },
	{ label: "Haravan (E-Commerce)", url: "haravan.com" },
	{ label: "Base.vn (B2B SaaS)", url: "base.vn" },
];

test("SAMPLE_DOMAINS contains 4 core industry presets", () => {
	assert.equal(SAMPLE_DOMAINS.length, 4);
	assert.equal(SAMPLE_DOMAINS[0].url, "vinhomes.vn");
	assert.equal(SAMPLE_DOMAINS[1].url, "topcv.vn");
});

// ---------------------------------------------------------------------------
// 3. Filter Preset Mapping & Multi-Table Dispatch Tests
// ---------------------------------------------------------------------------
function formatFilterStateFromPresets(presets: FilterPresets): {
	sourceFilter: string;
	intentFilter: string;
	searchQuery: string;
} {
	const sourceFilter = presets.platforms.length > 0 ? presets.platforms[0] : "all";
	const intentFilter = presets.intent || "all";
	const searchQuery = presets.target_industries.join(" ") || "";

	return { sourceFilter, intentFilter, searchQuery };
}

test("formatFilterStateFromPresets converts ReverseIcpResponse presets to table filters", () => {
	const mockPresets: FilterPresets = {
		platforms: ["batdongsan", "chotot"],
		intent: "BÁN",
		target_industries: ["Bất động sản cao cấp", "Biệt thự"],
		locations: ["Hà Nội"],
	};

	const state = formatFilterStateFromPresets(mockPresets);
	assert.equal(state.sourceFilter, "batdongsan");
	assert.equal(state.intentFilter, "BÁN");
	assert.equal(state.searchQuery, "Bất động sản cao cấp Biệt thự");
});

// ---------------------------------------------------------------------------
// 4. Chat Prompt Generation Helper Tests
// ---------------------------------------------------------------------------
function buildChatLeadDiscoveryUrl(workspaceId: string, prompt: string): string {
	return `/dashboard/${workspaceId}/new-chat?q=${encodeURIComponent(prompt)}`;
}

test("buildChatLeadDiscoveryUrl encodes prompt into chat URL", () => {
	const url = buildChatLeadDiscoveryUrl("1", "Tìm 30 leads Vinhomes Ocean Park");
	assert.equal(url, "/dashboard/1/new-chat?q=T%C3%ACm%2030%20leads%20Vinhomes%20Ocean%20Park");
});
