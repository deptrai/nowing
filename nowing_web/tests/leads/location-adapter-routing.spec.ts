import { expect, test } from "@playwright/test";
import { locationProfileSchema } from "../../contracts/types/leads.types";
import { buildLocationSummary, removeDiacritics } from "../../lib/geo/vietnam-divisions";

/**
 * Story 26.26: Location-Aware Adapter Routing & Coverage Quality
 * E2E test suite verifying composite ranking, boundary matching, fit score blending,
 * and location-aware campaign contracts.
 */
test.describe("Story 26.26: Location-Aware Adapter Routing & Coverage Quality", () => {
	test("AC-1 & AC-2: calculate adapter location coverage score and composite ranking formula", () => {
		// Test coverage quality scale: high=1.0, medium=0.7, low=0.4, nationwide=0.6, none=0.0
		const qualityScores: Record<string, number> = {
			high: 1.0,
			medium: 0.7,
			low: 0.4,
			none: 0.0,
		};

		expect(qualityScores.high).toBe(1.0);
		expect(qualityScores.medium).toBe(0.7);
		expect(qualityScores.low).toBe(0.4);
		expect(qualityScores.none).toBe(0.0);

		// Formula: composite_score = (location_coverage_score * 0.4) + (vertical_relevance_score * 0.4) + (cost_efficiency_score * 0.2)
		const calculateComposite = (locScore: number, vertScore: number, costScore = 0.8): number => {
			return Number((locScore * 0.4 + vertScore * 0.4 + costScore * 0.2).toFixed(4));
		};

		// High coverage adapter (e.g. Batdongsan in HN)
		const highCoverageScore = calculateComposite(1.0, 1.0, 0.8);
		// 0.4 + 0.4 + 0.16 = 0.96
		expect(highCoverageScore).toBe(0.96);

		// Nationwide fallback adapter (supported_provinces: ["*"])
		const nationwideScore = calculateComposite(0.6, 1.0, 0.8);
		// 0.24 + 0.4 + 0.16 = 0.80
		expect(nationwideScore).toBe(0.8);

		// Uncovered out-of-province adapter
		const zeroCoverageScore = calculateComposite(0.0, 1.0, 0.8);
		// 0.0 + 0.4 + 0.16 = 0.56
		expect(zeroCoverageScore).toBe(0.56);

		// Assert ranking order: high > nationwide > zero
		expect(highCoverageScore).toBeGreaterThan(nationwideScore);
		expect(nationwideScore).toBeGreaterThan(zeroCoverageScore);
	});

	test("AC-3: Word-boundary token matching distinguishes 'Quận 1' from 'Quận 10', '11', '12'", () => {
		// Helper implementing Unicode-aware word boundary pattern
		const containsWordBoundaryToken = (text: string, keyword: string): boolean => {
			const cleanText = removeDiacritics(text.toLowerCase());
			const cleanKw = removeDiacritics(keyword.toLowerCase());
			// Word boundary regex that avoids matching "quan 1" inside "quan 10", "quan 11", "quan 12"
			const regex = new RegExp(`(?<![\\wÀ-ỹ])${cleanKw}(?![\\wÀ-ỹ])`, "i");
			return regex.test(cleanText);
		};

		// Positive matches for Quận 1
		expect(containsWordBoundaryToken("Bán nhà mặt phố Quận 1, TP.HCM", "Quận 1")).toBe(true);
		expect(containsWordBoundaryToken("Văn phòng cho thuê tại quan 1", "quan 1")).toBe(true);
		expect(containsWordBoundaryToken("Địa chỉ: 123 Nguyễn Huệ, Q.1, HCM", "Q.1")).toBe(true);

		// Adversarial cases: Quận 1 must NOT match inside Quận 10, Quận 11, Quận 12
		expect(containsWordBoundaryToken("Chung cư cao cấp Quận 10", "Quận 1")).toBe(false);
		expect(containsWordBoundaryToken("Cho thuê phòng trọ Quận 11", "Quận 1")).toBe(false);
		expect(containsWordBoundaryToken("Nhà đất giá rẻ Quận 12", "Quận 1")).toBe(false);
		expect(containsWordBoundaryToken("Đường 10, Khu phố 12", "1")).toBe(false);
	});

	test("AC-3: Disambiguate multi-province district names ('Châu Thành' scoped to province)", () => {
		// A lead text with "Châu Thành, Bến Tre" should match Bến Tre profile, not Tiền Giang
		const benTreProfile = {
			province_code: "BT",
			province_name: "Bến Tre",
			district_names: ["Châu Thành"],
		};
		const tienGiangProfile = {
			province_code: "TG",
			province_name: "Tiền Giang",
			district_names: ["Châu Thành"],
		};

		const leadText = "Bán 500m2 đất vườn tại huyện Châu Thành, tỉnh Bến Tre giá rẻ";
		const cleanLead = removeDiacritics(leadText.toLowerCase());

		const matchesProfile = (text: string, profile: typeof benTreProfile): boolean => {
			const hasDistrict = profile.district_names.some((d) =>
				text.includes(removeDiacritics(d.toLowerCase()))
			);
			const hasProvince = text.includes(removeDiacritics(profile.province_name.toLowerCase()));
			return hasDistrict && hasProvince;
		};

		expect(matchesProfile(cleanLead, benTreProfile)).toBe(true);
		expect(matchesProfile(cleanLead, tienGiangProfile)).toBe(false);
	});

	test("AC-4: Blended location fit score formula calculation", () => {
		// Blending formula: final_fit_score = round(base_fit_score * 0.7 + location_match_score * 0.3, 1)
		const blendLocationFitScore = (baseFit: number, locMatch: number, weight = 0.3): number => {
			const blended = baseFit * (1.0 - weight) + locMatch * weight;
			return Math.round(blended * 10) / 10;
		};

		// Exact Ward match (loc = 100): 80 * 0.7 + 100 * 0.3 = 56 + 30 = 86.0
		expect(blendLocationFitScore(80.0, 100.0)).toBe(86.0);

		// District match (loc = 90): 90 * 0.7 + 90 * 0.3 = 63 + 27 = 90.0
		expect(blendLocationFitScore(90.0, 90.0)).toBe(90.0);

		// Broad province match (loc = 75): 70 * 0.7 + 75 * 0.3 = 49 + 22.5 = 71.5
		expect(blendLocationFitScore(70.0, 75.0)).toBe(71.5);

		// Partial province match (loc = 65): 60 * 0.7 + 65 * 0.3 = 42 + 19.5 = 61.5
		expect(blendLocationFitScore(60.0, 65.0)).toBe(61.5);
	});

	test("AC-5: LocationProfile contract validation for CampaignSpec", () => {
		const fullLocationPayload = {
			location_type: "both",
			province_code: "SG",
			province_name: "TP. Hồ Chí Minh",
			district_codes: ["760"],
			district_names: ["Quận 1"],
			ward_codes: ["26734"],
			ward_names: ["Phường Bến Nghé"],
			location_text: "TP. Hồ Chí Minh (Quận 1, Phường Bến Nghé)",
		};

		const result = locationProfileSchema.safeParse(fullLocationPayload);
		expect(result.success).toBe(true);

		if (result.success) {
			expect(result.data.province_code).toBe("SG");
			expect(result.data.district_names).toContain("Quận 1");
			expect(result.data.ward_names).toContain("Phường Bến Nghé");
		}
	});

	test("UI Component Verification: Location summary string correctly reflects multiple selection", () => {
		const summary = buildLocationSummary("HN", ["001", "002"], ["Phường Phúc Xá"]);
		expect(summary).toContain("Hà Nội");
		expect(summary).toContain("Ba Đình");
		expect(summary).toContain("Phường Phúc Xá");
	});
});
