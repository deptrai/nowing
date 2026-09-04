import { expect, test } from "@playwright/test";
import {
	buildLocationSummary,
	removeDiacritics,
	searchProvinces,
} from "../../lib/geo/vietnam-divisions";

test.describe("Story 26.25: Customer Location Profile Selector", () => {
	test("diacritic normalization and alias matching work correctly", () => {
		expect(removeDiacritics("Hà Nội")).toBe("ha noi");
		expect(removeDiacritics("TP. Hồ Chí Minh")).toBe("tp. ho chi minh");
		expect(removeDiacritics("Đà Nẵng")).toBe("da nang");

		// Search by alias
		const hcmResults = searchProvinces("sg");
		expect(hcmResults.some((p) => p.code === "SG")).toBe(true);

		const hnResults = searchProvinces("hn");
		expect(hnResults.some((p) => p.code === "HN")).toBe(true);

		const daNangResults = searchProvinces("da nang");
		expect(daNangResults.some((p) => p.code === "DN")).toBe(true);
	});

	test("buildLocationSummary formats human readable location string", () => {
		// Province only
		expect(buildLocationSummary("HN")).toBe("Hà Nội");

		// Province with districts
		const summary = buildLocationSummary("SG", ["760", "769"]);
		expect(summary).toContain("TP. Hồ Chí Minh");
		expect(summary).toContain("Quận 1");
		expect(summary).toContain("Thành phố Thủ Đức");
	});
});
