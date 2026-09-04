import { expect, test } from "@playwright/test";
import { locationProfileSchema } from "../../contracts/types/leads.types";
import {
	buildLocationSummary,
	removeDiacritics,
	searchProvinces,
} from "../../lib/geo/vietnam-divisions";

test.describe("Story 26.25: Customer Location Profile Selector", () => {
	test("diacritic normalization and alias matching work correctly (AC-3)", () => {
		expect(removeDiacritics("Hà Nội")).toBe("ha noi");
		expect(removeDiacritics("TP. Hồ Chí Minh")).toBe("tp. ho chi minh");
		expect(removeDiacritics("Đà Nẵng")).toBe("da nang");

		// Search by alias and district name/code
		const hcmResults = searchProvinces("sg");
		expect(hcmResults.some((p) => p.code === "SG")).toBe(true);

		const hnResults = searchProvinces("hn");
		expect(hnResults.some((p) => p.code === "HN")).toBe(true);

		const daNangResults = searchProvinces("da nang");
		expect(daNangResults.some((p) => p.code === "DN")).toBe(true);

		// Search by district name within province (AC-3)
		const districtSearch = searchProvinces("Cầu Giấy");
		expect(districtSearch.some((p) => p.code === "HN")).toBe(true);

		const districtCodeSearch = searchProvinces("760");
		expect(districtCodeSearch.some((p) => p.code === "SG")).toBe(true);
	});

	test("buildLocationSummary formats human readable location string with districts and wards (AC-5)", () => {
		// Province only
		expect(buildLocationSummary("HN")).toBe("Hà Nội");

		// Province with districts
		const summary = buildLocationSummary("SG", ["760", "769"]);
		expect(summary).toBe("TP. Hồ Chí Minh (Quận 1, Thành phố Thủ Đức)");

		// Province with districts and custom wards (single parenthetical format)
		const withWards = buildLocationSummary("SG", ["760"], ["Phường Bến Nghé"]);
		expect(withWards).toBe("TP. Hồ Chí Minh (Quận 1, Phường Bến Nghé)");
	});

	test("locationProfileSchema enforces required province validation message (AC-5)", () => {
		const emptyPayload = {
			location_type: "both",
			province_code: "",
			province_name: "",
			district_codes: [],
			district_names: [],
			ward_codes: [],
			ward_names: [],
			location_text: "",
		};

		const parsed = locationProfileSchema.safeParse(emptyPayload);
		expect(parsed.success).toBe(false);
		if (!parsed.success) {
			const errorMsgs = parsed.error.issues.map((i) => i.message);
			expect(errorMsgs).toContain("Vui lòng chọn ít nhất một Tỉnh / Thành phố");
		}

		const validPayload = {
			location_type: "both",
			province_code: "SG",
			province_name: "TP. Hồ Chí Minh",
			district_codes: ["760"],
			district_names: ["Quận 1"],
			ward_codes: [],
			ward_names: [],
			location_text: "TP. Hồ Chí Minh (Quận 1)",
		};

		const validResult = locationProfileSchema.safeParse(validPayload);
		expect(validResult.success).toBe(true);
	});
});
