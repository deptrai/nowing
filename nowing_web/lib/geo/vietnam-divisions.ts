/**
 * Vietnamese Administrative Divisions Catalog & Geo Helpers (Story 26.25)
 */

export interface District {
	code: string;
	name: string;
	wards?: string[];
}

export interface Province {
	code: string;
	name: string;
	aliases: string[];
	districts: District[];
}

export const QUICK_LOCATIONS = [
	{ code: "HN", label: "Hà Nội" },
	{ code: "SG", label: "TP.HCM" },
	{ code: "DN", label: "Đà Nẵng" },
	{ code: "HP", label: "Hải Phòng" },
	{ code: "CT", label: "Cần Thơ" },
] as const;

export const VIETNAM_PROVINCES: Province[] = [
	{
		code: "HN",
		name: "Hà Nội",
		aliases: ["hanoi", "ha noi", "hn"],
		districts: [
			{ code: "001", name: "Ba Đình" },
			{ code: "002", name: "Hoàn Kiếm" },
			{ code: "003", name: "Tây Hồ" },
			{ code: "004", name: "Long Biên" },
			{ code: "005", name: "Cầu Giấy" },
			{ code: "006", name: "Đống Đa" },
			{ code: "007", name: "Hai Bà Trưng" },
			{ code: "008", name: "Hoàng Mai" },
			{ code: "009", name: "Thanh Xuân" },
			{ code: "016", name: "Sóc Sơn" },
			{ code: "017", name: "Đông Anh" },
			{ code: "018", name: "Gia Lâm" },
			{ code: "019", name: "Nam Từ Liêm" },
			{ code: "020", name: "Thanh Trì" },
			{ code: "021", name: "Bắc Từ Liêm" },
			{ code: "268", name: "Hà Đông" },
			{ code: "269", name: "Sơn Tây" },
			{ code: "271", name: "Ba Vì" },
			{ code: "272", name: "Phúc Thọ" },
			{ code: "273", name: "Đan Phượng" },
			{ code: "274", name: "Hoài Đức" },
			{ code: "275", name: "Quốc Oai" },
			{ code: "276", name: "Thạch Thất" },
			{ code: "277", name: "Chương Mỹ" },
			{ code: "278", name: "Thanh Oai" },
			{ code: "279", name: "Thường Tín" },
			{ code: "280", name: "Phú Xuyên" },
			{ code: "281", name: "Ứng Hòa" },
			{ code: "282", name: "Mỹ Đức" },
		],
	},
	{
		code: "SG",
		name: "TP. Hồ Chí Minh",
		aliases: ["saigon", "sai gon", "hcm", "tphcm", "ho chi minh", "sg"],
		districts: [
			{ code: "760", name: "Quận 1" },
			{ code: "761", name: "Quận 12" },
			{ code: "764", name: "Gò Vấp" },
			{ code: "765", name: "Bình Thạnh" },
			{ code: "766", name: "Tân Bình" },
			{ code: "767", name: "Tân Phú" },
			{ code: "768", name: "Phú Nhuận" },
			{ code: "769", name: "Thành phố Thủ Đức" },
			{ code: "770", name: "Quận 3" },
			{ code: "771", name: "Quận 10" },
			{ code: "772", name: "Quận 11" },
			{ code: "773", name: "Quận 4" },
			{ code: "774", name: "Quận 5" },
			{ code: "775", name: "Quận 6" },
			{ code: "776", name: "Quận 8" },
			{ code: "777", name: "Bình Tân" },
			{ code: "778", name: "Quận 7" },
			{ code: "783", name: "Củ Chi" },
			{ code: "784", name: "Hóc Môn" },
			{ code: "785", name: "Bình Chánh" },
			{ code: "786", name: "Nhà Bè" },
			{ code: "787", name: "Cần Giờ" },
		],
	},
	{
		code: "DN",
		name: "Đà Nẵng",
		aliases: ["danang", "da nang", "dn"],
		districts: [
			{ code: "490", name: "Liên Chiểu" },
			{ code: "491", name: "Thanh Khê" },
			{ code: "492", name: "Hải Châu" },
			{ code: "493", name: "Sơn Trà" },
			{ code: "494", name: "Ngũ Hành Sơn" },
			{ code: "495", name: "Cẩm Lệ" },
			{ code: "497", name: "Hòa Vang" },
			{ code: "498", name: "Hoàng Sa" },
		],
	},
	{
		code: "HP",
		name: "Hải Phòng",
		aliases: ["haiphong", "hai phong", "hp"],
		districts: [
			{ code: "303", name: "Hồng Bàng" },
			{ code: "304", name: "Ngô Quyền" },
			{ code: "305", name: "Lê Chân" },
			{ code: "306", name: "Hải An" },
			{ code: "307", name: "Kiến An" },
			{ code: "308", name: "Đồ Sơn" },
			{ code: "309", name: "Dương Kinh" },
			{ code: "311", name: "Thủy Nguyên" },
			{ code: "312", name: "An Dương" },
			{ code: "313", name: "An Lão" },
			{ code: "314", name: "Kiến Thụy" },
			{ code: "315", name: "Tiên Lãng" },
			{ code: "316", name: "Vĩnh Bảo" },
			{ code: "317", name: "Cát Hải" },
			{ code: "318", name: "Bạch Long Vĩ" },
		],
	},
	{
		code: "CT",
		name: "Cần Thơ",
		aliases: ["cantho", "can tho", "ct"],
		districts: [
			{ code: "916", name: "Ninh Kiều" },
			{ code: "917", name: "Ô Môn" },
			{ code: "918", name: "Bình Thủy" },
			{ code: "919", name: "Cái Răng" },
			{ code: "923", name: "Thốt Nốt" },
			{ code: "924", name: "Vĩnh Thạnh" },
			{ code: "925", name: "Cờ Đỏ" },
			{ code: "926", name: "Phong Điền" },
			{ code: "927", name: "Thới Lai" },
		],
	},
	{
		code: "BD",
		name: "Bình Dương",
		aliases: ["binhduong", "binh duong", "bd"],
		districts: [
			{ code: "718", name: "Thủ Dầu Một" },
			{ code: "719", name: "Bàu Bàng" },
			{ code: "720", name: "Dầu Tiếng" },
			{ code: "721", name: "Bến Cát" },
			{ code: "722", name: "Phú Giáo" },
			{ code: "723", name: "Tân Uyên" },
			{ code: "724", name: "Dĩ An" },
			{ code: "725", name: "Thuận An" },
			{ code: "726", name: "Bắc Tân Uyên" },
		],
	},
	{
		code: "DNA",
		name: "Đồng Nai",
		aliases: ["dongnai", "dong nai"],
		districts: [
			{ code: "731", name: "Biên Hòa" },
			{ code: "732", name: "Long Khánh" },
			{ code: "734", name: "Tân Phú" },
			{ code: "735", name: "Vĩnh Cửu" },
			{ code: "736", name: "Định Quán" },
			{ code: "737", name: "Trảng Bom" },
			{ code: "738", name: "Thống Nhất" },
			{ code: "739", name: "Cẩm Mỹ" },
			{ code: "740", name: "Long Thành" },
			{ code: "741", name: "Xuân Lộc" },
			{ code: "742", name: "Nhơn Trạch" },
		],
	},
	{
		code: "VT",
		name: "Bà Rịa - Vũng Tàu",
		aliases: ["vungtau", "vung tau", "ba ria", "vt"],
		districts: [
			{ code: "747", name: "Vũng Tàu" },
			{ code: "748", name: "Bà Rịa" },
			{ code: "750", name: "Châu Đức" },
			{ code: "751", name: "Xuyên Mộc" },
			{ code: "752", name: "Long Điền" },
			{ code: "753", name: "Đất Đỏ" },
			{ code: "754", name: "Phú Mỹ" },
			{ code: "755", name: "Côn Đảo" },
		],
	},
	{
		code: "KH",
		name: "Khánh Hòa",
		aliases: ["nhatrang", "nha trang", "khanh hoa"],
		districts: [
			{ code: "568", name: "Nha Trang" },
			{ code: "569", name: "Cam Ranh" },
			{ code: "570", name: "Cam Lâm" },
			{ code: "571", name: "Vạn Ninh" },
			{ code: "572", name: "Ninh Hòa" },
			{ code: "573", name: "Khánh Vĩnh" },
			{ code: "574", name: "Diên Khánh" },
			{ code: "575", name: "Khánh Sơn" },
			{ code: "576", name: "Trường Sa" },
		],
	},
	{
		code: "LD",
		name: "Lâm Đồng",
		aliases: ["dalat", "da lat", "lam dong"],
		districts: [
			{ code: "672", name: "Đà Lạt" },
			{ code: "673", name: "Bảo Lộc" },
			{ code: "674", name: "Đam Rông" },
			{ code: "675", name: "Lạc Dương" },
			{ code: "676", name: "Lâm Hà" },
			{ code: "677", name: "Đơn Dương" },
			{ code: "678", name: "Đức Trọng" },
			{ code: "679", name: "Di Linh" },
			{ code: "680", name: "Bảo Lâm" },
			{ code: "681", name: "Đạ Huoai" },
			{ code: "682", name: "Đạ Tẻh" },
			{ code: "683", name: "Cát Tiên" },
		],
	},
];

/**
 * Remove Vietnamese accents/diacritics and return lowercase ASCII string.
 */
export function removeDiacritics(text: string): string {
	if (!text) return "";
	return text.normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[đĐ]/g, "d").toLowerCase().trim();
}

/**
 * Match a user search query against province names, aliases, and district names/codes.
 */
export function searchProvinces(query: string): Province[] {
	const cleanQuery = removeDiacritics(query);
	if (!cleanQuery) return VIETNAM_PROVINCES;

	return VIETNAM_PROVINCES.filter((p) => {
		const cleanName = removeDiacritics(p.name);
		const cleanCode = p.code.toLowerCase();
		if (cleanName.includes(cleanQuery) || cleanCode.includes(cleanQuery)) return true;
		if (p.aliases.some((alias) => removeDiacritics(alias).includes(cleanQuery))) return true;

		// Match district name or district code inside the province
		return p.districts.some((d) => {
			const dName = removeDiacritics(d.name);
			const dCode = d.code.toLowerCase();
			return dName.includes(cleanQuery) || dCode.includes(cleanQuery);
		});
	});
}

/**
 * Build a concise location summary string from selected IDs and wards.
 */
export function buildLocationSummary(
	provinceCode: string,
	districtCodes: string[] = [],
	wardNames: string[] = []
): string {
	if (!provinceCode) return "";
	const pCodeUpper = provinceCode.toUpperCase();
	const prov = VIETNAM_PROVINCES.find((p) => p.code.toUpperCase() === pCodeUpper);
	if (!prov) return provinceCode;

	const parts: string[] = [];

	if (districtCodes && districtCodes.length > 0) {
		const selectedNames = prov.districts
			.filter((d) => districtCodes.includes(d.code))
			.map((d) => d.name);
		parts.push(...selectedNames);
	}

	if (wardNames && wardNames.length > 0) {
		const cleanWards = wardNames.map((w) => w.trim()).filter(Boolean);
		parts.push(...cleanWards);
	}

	if (parts.length > 0) {
		return `${prov.name} (${parts.join(", ")})`;
	}

	return prov.name;
}
