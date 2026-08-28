"use client";

import {
	ArrowRight,
	Bot,
	Building,
	Calendar,
	Check,
	ChevronLeft,
	Coins,
	Cpu,
	Filter,
	Globe,
	Layers,
	Loader2,
	MapPin,
	Play,
	Plus,
	Rocket,
	ShieldCheck,
	Sparkles,
	Target,
	X,
	Zap,
} from "lucide-react";
import type React from "react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type {
	Campaign,
	CampaignCreateInput,
	CampaignIntent,
	IcpConfig,
	IcpVerticalTemplate,
	LaunchConfig,
	SourceBudgetConfig,
} from "@/contracts/types/campaign.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";

export interface CampaignBuilderProps {
	workspaceId: string | number;
	onCampaignCreated?: (campaign: Campaign) => void;
	onCancel?: () => void;
}

const VERTICAL_PRESETS: Record<
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

const AVAILABLE_SOURCES = [
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

export const CampaignBuilder: React.FC<CampaignBuilderProps> = ({
	workspaceId,
	onCampaignCreated,
	onCancel,
}) => {
	const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [isAnalyzingIcp, setIsAnalyzingIcp] = useState(false);

	// Campaign Form State
	const [campaignName, setCampaignName] = useState("Chiến dịch tìm kiếm Lead ICP Q3");
	const [campaignDesc, setCampaignDesc] = useState(
		"Tự động quét tín hiệu thị trường và chấm điểm Fit Score tự động"
	);

	// Step 1: ICP Builder State
	const [selectedTemplate, setSelectedTemplate] = useState<IcpVerticalTemplate>("b2b_saas");
	const [targetIndustries, setTargetIndustries] = useState<string[]>(
		VERTICAL_PRESETS.b2b_saas.industries
	);
	const [industryInput, setIndustryInput] = useState("");
	const [locations, setLocations] = useState<string[]>(VERTICAL_PRESETS.b2b_saas.locations);
	const [locationInput, setLocationInput] = useState("");
	const [companySize, setCompanySize] = useState("50-200 nhân sự");
	const [techStack, setTechStack] = useState<string[]>(VERTICAL_PRESETS.b2b_saas.techStack);
	const [techInput, setTechInput] = useState("");
	const [selectedIntents, setSelectedIntents] = useState<CampaignIntent[]>(
		VERTICAL_PRESETS.b2b_saas.intents
	);
	const [negativeKeywords, setNegativeKeywords] = useState<string[]>([
		"tuyển dụng lừa đảo",
		"việc nhẹ lương cao",
	]);
	const [negativeInput, setNegativeInput] = useState("");
	const [reverseIcpUrl, setReverseIcpUrl] = useState("");
	const [customInstructions, _setCustomInstructions] = useState("");

	// Step 2: Sources & Budget State
	const [selectedSources, setSelectedSources] = useState<string[]>(
		VERTICAL_PRESETS.b2b_saas.sources
	);
	const [expectedLeadsTarget, setExpectedLeadsTarget] = useState<number>(150);
	const [minFitScore, setMinFitScore] = useState<number>(70);
	const [minIntentScore, setMinIntentScore] = useState<number>(60);
	const [maxContactsPerLead, setMaxContactsPerLead] = useState<number>(3);
	const [excludeDnc, setExcludeDnc] = useState<boolean>(true);
	const [autoUnlockPhones, setAutoUnlockPhones] = useState<boolean>(false);
	const [maxDailySpend, _setMaxDailySpend] = useState<number>(500000);

	// Step 3: Launch Configuration State
	const [scheduleType, setScheduleType] = useState<"once" | "recurring">("once");
	const [cronExp, setCronExp] = useState("0 8 * * 1-5"); // 8:00 AM weekdays
	const [autoStart, _setAutoStart] = useState(true);
	const [exportDestination, setExportDestination] = useState<
		"workspace" | "crm" | "lark" | "sheets"
	>("workspace");

	// Estimated lead calculation
	const estimatedCost = useMemo(() => {
		const costPerLead = autoUnlockPhones ? 5000 : 1500;
		return expectedLeadsTarget * costPerLead;
	}, [expectedLeadsTarget, autoUnlockPhones]);

	const handleTemplateSelect = (templateKey: IcpVerticalTemplate) => {
		setSelectedTemplate(templateKey);
		const preset = VERTICAL_PRESETS[templateKey];
		setTargetIndustries(preset.industries);
		setLocations(preset.locations);
		setCompanySize(preset.companySize);
		setTechStack(preset.techStack);
		setSelectedIntents(preset.intents);
		setSelectedSources(preset.sources);
	};

	const handleAddTag = (
		item: string,
		list: string[],
		setter: (val: string[]) => void,
		inputSetter: (val: string) => void
	) => {
		const trimmed = item.trim();
		if (trimmed && !list.includes(trimmed)) {
			setter([...list, trimmed]);
			inputSetter("");
		}
	};

	const handleRemoveTag = (index: number, list: string[], setter: (val: string[]) => void) => {
		setter(list.filter((_, i) => i !== index));
	};

	const handleToggleIntent = (intent: CampaignIntent) => {
		if (selectedIntents.includes(intent)) {
			if (selectedIntents.length > 1) {
				setSelectedIntents(selectedIntents.filter((i) => i !== intent));
			} else {
				toast.error("Phải chọn ít nhất 1 loại Ý định (Intent)");
			}
		} else {
			setSelectedIntents([...selectedIntents, intent]);
		}
	};

	const handleToggleSource = (sourceId: string) => {
		if (selectedSources.includes(sourceId)) {
			if (selectedSources.length > 1) {
				setSelectedSources(selectedSources.filter((s) => s !== sourceId));
			} else {
				toast.error("Phải chọn ít nhất 1 nguồn thu thập");
			}
		} else {
			setSelectedSources([...selectedSources, sourceId]);
		}
	};

	const handleAnalyzeReverseIcp = async () => {
		if (!reverseIcpUrl) {
			toast.error("Vui lòng nhập URL website đối thủ hoặc khách hàng mẫu");
			return;
		}

		try {
			setIsAnalyzingIcp(true);
			toast.info("Đang trích xuất ICP tự động bằng AI qua website...");
			const res = await leadsApiService.analyzeReverseIcp(
				workspaceId,
				reverseIcpUrl,
				customInstructions
			);
			if (res) {
				if (res.industry && !targetIndustries.includes(res.industry)) {
					setTargetIndustries((prev) => [...prev, res.industry]);
				}
				if (res.filter_presets?.target_industries?.length) {
					setTargetIndustries((prev) =>
						Array.from(new Set([...prev, ...res.filter_presets.target_industries]))
					);
				}
				if (res.filter_presets?.locations?.length) {
					setLocations((prev) => Array.from(new Set([...prev, ...res.filter_presets.locations])));
				}
				if (res.negative_keywords?.length) {
					setNegativeKeywords((prev) => Array.from(new Set([...prev, ...res.negative_keywords])));
				}
				if (res.company_name) {
					setCampaignName(`Chiến dịch ICP từ: ${res.company_name}`);
				}
				toast.success("Đã phân tích và điền tự động các tiêu chí ICP!");
			}
		} catch (_err) {
			toast.error("Không thể phân tích Reverse ICP từ URL này. Vui lòng kiểm tra lại đường dẫn.");
		} finally {
			setIsAnalyzingIcp(false);
		}
	};

	const handleSaveCampaign = async (andLaunch = false) => {
		if (!campaignName.trim()) {
			toast.error("Vui lòng nhập tên chiến dịch");
			return;
		}
		if (selectedSources.length === 0) {
			toast.error("Vui lòng chọn ít nhất 1 nguồn dữ liệu");
			return;
		}

		try {
			setIsSubmitting(true);
			const icpConfig: IcpConfig = {
				template: selectedTemplate,
				target_industries: targetIndustries,
				locations,
				company_size_range: companySize,
				tech_stack: techStack,
				intents: selectedIntents,
				negative_keywords: negativeKeywords,
				reverse_icp_url: reverseIcpUrl || null,
				custom_instructions: customInstructions || null,
			};

			const sourceBudgetConfig: SourceBudgetConfig = {
				sources: selectedSources,
				expected_leads_target: expectedLeadsTarget,
				max_daily_spend_vnd: maxDailySpend,
				min_fit_score: minFitScore,
				min_intent_score: minIntentScore,
				max_contacts_per_lead: maxContactsPerLead,
				exclude_dnc: excludeDnc,
				auto_unlock_verified_phones: autoUnlockPhones,
			};

			const launchConfig: LaunchConfig = {
				schedule_type: scheduleType,
				cron_expression: scheduleType === "recurring" ? cronExp : null,
				auto_start: autoStart,
				export_destination: exportDestination,
				notification_webhook: null,
			};

			const payload: CampaignCreateInput = {
				name: campaignName,
				description: campaignDesc,
				icp_config: icpConfig,
				source_budget_config: sourceBudgetConfig,
				launch_config: launchConfig,
			};

			const created = await leadsApiService.createCampaign(workspaceId, payload);
			if (created) {
				if (andLaunch) {
					await leadsApiService.launchCampaign(workspaceId, created.id);
					toast.success(`Đã tạo và kích hoạt chiến dịch "${created.name}" thành công!`);
				} else {
					toast.success(`Đã lưu chiến dịch "${created.name}" dưới dạng bản nháp`);
				}
				onCampaignCreated?.(created);
			}
		} catch (_err) {
			toast.error("Không thể lưu chiến dịch. Vui lòng thử lại.");
		} finally {
			setIsSubmitting(false);
		}
	};

	return (
		<div className="space-y-6 max-w-6xl mx-auto pb-12">
			{/* Header & Steps Progress */}
			<div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-2xl bg-zinc-900/70 border border-zinc-800 shadow-xl backdrop-blur-md">
				<div>
					<div className="flex items-center gap-2 mb-1">
						<span className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
							<Target className="w-5 h-5" />
						</span>
						<h1 className="text-xl font-bold text-zinc-100">Campaign Builder Wizard</h1>
						<Badge
							variant="outline"
							className="bg-emerald-950/40 text-emerald-400 border-emerald-800/60 font-mono text-xs"
						>
							Story 21.15
						</Badge>
					</div>
					<p className="text-xs text-zinc-400">
						Thiết lập tiêu chí ICP, phân bổ nguồn dữ liệu đa kênh & kích hoạt SDR Pipeline tự động
					</p>
				</div>

				{/* Wizard Steps Indicator */}
				<div className="flex items-center gap-2">
					<button
						type="button"
						onClick={() => setCurrentStep(1)}
						className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
							currentStep === 1
								? "bg-emerald-500 text-black shadow-md shadow-emerald-500/20"
								: "bg-zinc-800/80 text-zinc-400 hover:text-zinc-200"
						}`}
					>
						<span className="w-4 h-4 rounded-full bg-black/20 flex items-center justify-center text-[10px]">
							1
						</span>
						<span>ICP Builder</span>
					</button>
					<ArrowRight className="w-3 h-3 text-zinc-600" />
					<button
						type="button"
						onClick={() => setCurrentStep(2)}
						className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
							currentStep === 2
								? "bg-emerald-500 text-black shadow-md shadow-emerald-500/20"
								: "bg-zinc-800/80 text-zinc-400 hover:text-zinc-200"
						}`}
					>
						<span className="w-4 h-4 rounded-full bg-black/20 flex items-center justify-center text-[10px]">
							2
						</span>
						<span>Nguồn & Ngân sách</span>
					</button>
					<ArrowRight className="w-3 h-3 text-zinc-600" />
					<button
						type="button"
						onClick={() => setCurrentStep(3)}
						className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-all ${
							currentStep === 3
								? "bg-emerald-500 text-black shadow-md shadow-emerald-500/20"
								: "bg-zinc-800/80 text-zinc-400 hover:text-zinc-200"
						}`}
					>
						<span className="w-4 h-4 rounded-full bg-black/20 flex items-center justify-center text-[10px]">
							3
						</span>
						<span>Launch & Lên lịch</span>
					</button>
				</div>
			</div>

			{/* ================= STEP 1: ICP BUILDER ================= */}
			{currentStep === 1 && (
				<div className="space-y-6">
					<Card className="bg-zinc-900/60 border-zinc-800/80">
						<CardHeader>
							<CardTitle className="text-base flex items-center gap-2 text-zinc-100">
								<Layers className="w-4 h-4 text-emerald-400" />
								<span>1. Chọn Mẫu Ngành Dọc (Vertical Template)</span>
							</CardTitle>
							<CardDescription className="text-xs text-zinc-400">
								Chọn ngành mẫu để Nowing tự động cấu hình bộ từ khóa và tiêu chí đo lường phù hợp
							</CardDescription>
						</CardHeader>
						<CardContent>
							<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
								{(Object.keys(VERTICAL_PRESETS) as IcpVerticalTemplate[]).map((key) => {
									const preset = VERTICAL_PRESETS[key];
									const isSelected = selectedTemplate === key;
									return (
										<button
											key={key}
											type="button"
											onClick={() => handleTemplateSelect(key)}
											className={`text-left p-4 rounded-xl border cursor-pointer transition-all ${
												isSelected
													? "bg-emerald-500/10 border-emerald-500/50 ring-1 ring-emerald-500 shadow-md"
													: "bg-zinc-950/40 border-zinc-800/80 hover:border-zinc-700 text-zinc-300"
											}`}
										>
											<div className="flex items-center justify-between mb-1.5">
												<h4
													className={`text-xs font-bold ${isSelected ? "text-emerald-400" : "text-zinc-200"}`}
												>
													{preset.label}
												</h4>
												{isSelected && <Check className="w-3.5 h-3.5 text-emerald-400" />}
											</div>
											<p className="text-[11px] text-zinc-400 line-clamp-2">{preset.description}</p>
										</button>
									);
								})}
							</div>
						</CardContent>
					</Card>

					{/* Reverse ICP Quick Import */}
					<Card className="bg-gradient-to-r from-emerald-950/20 via-zinc-900/60 to-zinc-900/60 border-emerald-900/40">
						<CardHeader>
							<CardTitle className="text-sm flex items-center justify-between text-zinc-100">
								<span className="flex items-center gap-2">
									<Sparkles className="w-4 h-4 text-emerald-400" />
									<span>1-Click Reverse ICP từ Website</span>
								</span>
								<Badge
									variant="outline"
									className="text-[10px] bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
								>
									AI Powered
								</Badge>
							</CardTitle>
							<CardDescription className="text-xs text-zinc-400">
								Nhập website khách hàng lý tưởng hoặc đối thủ để AI tự động phân tích và trích xuất
								hồ sơ ICP
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div className="flex gap-2">
								<Input
									type="url"
									value={reverseIcpUrl}
									onChange={(e) => setReverseIcpUrl(e.target.value)}
									placeholder="https://example.com (URL công ty mục tiêu)"
									className="bg-zinc-950/80 border-zinc-800 text-xs"
								/>
								<Button
									type="button"
									disabled={isAnalyzingIcp || !reverseIcpUrl}
									onClick={handleAnalyzeReverseIcp}
									className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-semibold shrink-0"
								>
									{isAnalyzingIcp ? (
										<>
											<Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
											Đang phân tích...
										</>
									) : (
										<>
											<Bot className="w-3.5 h-3.5 mr-1.5" />
											Trích xuất ICP
										</>
									)}
								</Button>
							</div>
						</CardContent>
					</Card>

					{/* Detailed ICP Criteria */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
						{/* Left Column: Target Entities */}
						<Card className="bg-zinc-900/60 border-zinc-800/80">
							<CardHeader>
								<CardTitle className="text-sm flex items-center gap-2 text-zinc-100">
									<Building className="w-4 h-4 text-emerald-400" />
									<span>Ngành nghề & Địa lý mục tiêu</span>
								</CardTitle>
							</CardHeader>
							<CardContent className="space-y-4">
								{/* Industries */}
								<div>
									<Label className="text-xs text-zinc-300">Ngành nghề trọng tâm</Label>
									<div className="flex gap-2 mt-1.5">
										<Input
											value={industryInput}
											onChange={(e) => setIndustryInput(e.target.value)}
											onKeyDown={(e) => {
												if (e.key === "Enter") {
													e.preventDefault();
													handleAddTag(
														industryInput,
														targetIndustries,
														setTargetIndustries,
														setIndustryInput
													);
												}
											}}
											placeholder="Nhập ngành & nhấn Enter..."
											className="text-xs bg-zinc-950/70 border-zinc-800"
										/>
										<Button
											type="button"
											size="sm"
											variant="secondary"
											onClick={() =>
												handleAddTag(
													industryInput,
													targetIndustries,
													setTargetIndustries,
													setIndustryInput
												)
											}
										>
											<Plus className="w-3.5 h-3.5" />
										</Button>
									</div>
									<div className="flex flex-wrap gap-1.5 mt-2">
										{targetIndustries.map((ind, idx) => (
											<span
												key={ind}
												className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/20"
											>
												{ind}
												<X
													className="w-3 h-3 cursor-pointer hover:text-white"
													onClick={() =>
														handleRemoveTag(idx, targetIndustries, setTargetIndustries)
													}
												/>
											</span>
										))}
									</div>
								</div>

								{/* Locations */}
								<div>
									<Label className="text-xs text-zinc-300">Khu vực / Tỉnh thành</Label>
									<div className="flex gap-2 mt-1.5">
										<Input
											value={locationInput}
											onChange={(e) => setLocationInput(e.target.value)}
											onKeyDown={(e) => {
												if (e.key === "Enter") {
													e.preventDefault();
													handleAddTag(locationInput, locations, setLocations, setLocationInput);
												}
											}}
											placeholder="Hà Nội, TP.HCM, Bình Dương..."
											className="text-xs bg-zinc-950/70 border-zinc-800"
										/>
										<Button
											type="button"
											size="sm"
											variant="secondary"
											onClick={() =>
												handleAddTag(locationInput, locations, setLocations, setLocationInput)
											}
										>
											<Plus className="w-3.5 h-3.5" />
										</Button>
									</div>
									<div className="flex flex-wrap gap-1.5 mt-2">
										{locations.map((loc, idx) => (
											<span
												key={loc}
												className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] bg-zinc-800 text-zinc-300 border border-zinc-700"
											>
												<MapPin className="w-3 h-3 text-zinc-400" />
												{loc}
												<X
													className="w-3 h-3 cursor-pointer hover:text-white"
													onClick={() => handleRemoveTag(idx, locations, setLocations)}
												/>
											</span>
										))}
									</div>
								</div>

								{/* Company Size */}
								<div>
									<Label className="text-xs text-zinc-300">Quy mô nhân sự</Label>
									<select
										value={companySize}
										onChange={(e) => setCompanySize(e.target.value)}
										className="w-full mt-1.5 px-3 py-2 text-xs rounded-lg bg-zinc-950/70 border border-zinc-800 text-zinc-200 focus:ring-1 focus:ring-emerald-500"
									>
										<option value="1-10 nhân sự">1-10 nhân sự (Micro / Startups)</option>
										<option value="10-50 nhân sự">10-50 nhân sự (Small Business)</option>
										<option value="50-200 nhân sự">50-200 nhân sự (Medium Business)</option>
										<option value="200-500 nhân sự">200-500 nhân sự (Mid-Enterprise)</option>
										<option value="500+ nhân sự">500+ nhân sự (Enterprise / Corp)</option>
									</select>
								</div>
							</CardContent>
						</Card>

						{/* Right Column: Intent & Tech & Negative Keywords */}
						<Card className="bg-zinc-900/60 border-zinc-800/80">
							<CardHeader>
								<CardTitle className="text-sm flex items-center gap-2 text-zinc-100">
									<Target className="w-4 h-4 text-amber-400" />
									<span>Ý định thị trường & Từ khóa loại trừ</span>
								</CardTitle>
							</CardHeader>
							<CardContent className="space-y-4">
								{/* Intents */}
								<div>
									<Label className="text-xs text-zinc-300">
										Ý định tín hiệu mua bán (Market Intents)
									</Label>
									<div className="flex flex-wrap gap-2 mt-2">
										{(["BÁN", "MUA", "TUYỂN", "ĐẤU THẦU", "HỢP TÁC"] as CampaignIntent[]).map(
											(intent) => {
												const isSelected = selectedIntents.includes(intent);
												return (
													<button
														key={intent}
														type="button"
														onClick={() => handleToggleIntent(intent)}
														className={`px-3 py-1 text-xs font-semibold rounded-lg border transition-all ${
															isSelected
																? "bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-sm"
																: "bg-zinc-950/40 text-zinc-400 border-zinc-800 hover:border-zinc-700"
														}`}
													>
														🏷️ INTENT: {intent}
													</button>
												);
											}
										)}
									</div>
								</div>

								{/* Tech Stack */}
								<div>
									<Label className="text-xs text-zinc-300">Công nghệ & Công cụ (Tech Stack)</Label>
									<div className="flex gap-2 mt-1.5">
										<Input
											value={techInput}
											onChange={(e) => setTechInput(e.target.value)}
											onKeyDown={(e) => {
												if (e.key === "Enter") {
													e.preventDefault();
													handleAddTag(techInput, techStack, setTechStack, setTechInput);
												}
											}}
											placeholder="React, AWS, SAP, Salesforce..."
											className="text-xs bg-zinc-950/70 border-zinc-800"
										/>
										<Button
											type="button"
											size="sm"
											variant="secondary"
											onClick={() => handleAddTag(techInput, techStack, setTechStack, setTechInput)}
										>
											<Plus className="w-3.5 h-3.5" />
										</Button>
									</div>
									<div className="flex flex-wrap gap-1.5 mt-2">
										{techStack.map((tech, idx) => (
											<span
												key={tech}
												className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] bg-blue-500/10 text-blue-300 border border-blue-500/20"
											>
												<Cpu className="w-3 h-3 text-blue-400" />
												{tech}
												<X
													className="w-3 h-3 cursor-pointer hover:text-white"
													onClick={() => handleRemoveTag(idx, techStack, setTechStack)}
												/>
											</span>
										))}
									</div>
								</div>

								{/* Negative Keywords */}
								<div>
									<Label className="text-xs text-zinc-300">
										Từ khóa phủ định (Negative Keywords)
									</Label>
									<div className="flex gap-2 mt-1.5">
										<Input
											value={negativeInput}
											onChange={(e) => setNegativeInput(e.target.value)}
											onKeyDown={(e) => {
												if (e.key === "Enter") {
													e.preventDefault();
													handleAddTag(
														negativeInput,
														negativeKeywords,
														setNegativeKeywords,
														setNegativeInput
													);
												}
											}}
											placeholder="Từ khóa cần lọc bỏ (spam, lừa đảo...)"
											className="text-xs bg-zinc-950/70 border-zinc-800"
										/>
										<Button
											type="button"
											size="sm"
											variant="secondary"
											onClick={() =>
												handleAddTag(
													negativeInput,
													negativeKeywords,
													setNegativeKeywords,
													setNegativeInput
												)
											}
										>
											<Plus className="w-3.5 h-3.5" />
										</Button>
									</div>
									<div className="flex flex-wrap gap-1.5 mt-2">
										{negativeKeywords.map((neg, idx) => (
											<span
												key={neg}
												className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-[11px] bg-red-500/10 text-red-300 border border-red-500/20"
											>
												🚫 {neg}
												<X
													className="w-3 h-3 cursor-pointer hover:text-white"
													onClick={() =>
														handleRemoveTag(idx, negativeKeywords, setNegativeKeywords)
													}
												/>
											</span>
										))}
									</div>
								</div>
							</CardContent>
						</Card>
					</div>

					{/* Navigation Button */}
					<div className="flex justify-end gap-3 pt-4 border-t border-zinc-800">
						{onCancel && (
							<Button variant="ghost" onClick={onCancel} className="text-xs text-zinc-400">
								Hủy bỏ
							</Button>
						)}
						<Button
							type="button"
							onClick={() => setCurrentStep(2)}
							className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold px-6"
						>
							Tiếp tục: Nguồn & Ngân sách
							<ArrowRight className="w-3.5 h-3.5 ml-1.5" />
						</Button>
					</div>
				</div>
			)}

			{/* ================= STEP 2: SOURCES & BUDGET ================= */}
			{currentStep === 2 && (
				<div className="space-y-6">
					{/* Sources Multi-Selection */}
					<Card className="bg-zinc-900/60 border-zinc-800/80">
						<CardHeader>
							<CardTitle className="text-base flex items-center gap-2 text-zinc-100">
								<Globe className="w-4 h-4 text-emerald-400" />
								<span>2. Nguồn Thu Thập Tín Hiệu (Multi-Source Adapters)</span>
							</CardTitle>
							<CardDescription className="text-xs text-zinc-400">
								Chọn các kênh quét dữ liệu trực tiếp trong hệ sinh thái Nowing Lead Generation
							</CardDescription>
						</CardHeader>
						<CardContent>
							<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
								{AVAILABLE_SOURCES.map((src) => {
									const isSelected = selectedSources.includes(src.id);
									return (
										<button
											key={src.id}
											type="button"
											onClick={() => handleToggleSource(src.id)}
											className={`text-left p-4 rounded-xl border cursor-pointer transition-all ${
												isSelected
													? "bg-emerald-500/10 border-emerald-500/40 ring-1 ring-emerald-500/30"
													: "bg-zinc-950/40 border-zinc-800/80 hover:border-zinc-700"
											}`}
										>
											<div className="flex items-center justify-between mb-1.5">
												<div className="flex items-center gap-2 font-bold text-xs text-zinc-200">
													<span className="text-base">{src.icon}</span>
													<span>{src.name}</span>
												</div>
												<input
													type="checkbox"
													checked={isSelected}
													onChange={() => {}}
													className="rounded border-zinc-700 text-emerald-500 focus:ring-emerald-500"
												/>
											</div>
											<p className="text-[11px] text-zinc-400">{src.description}</p>
										</button>
									);
								})}
							</div>
						</CardContent>
					</Card>

					{/* Thresholds & Quality Filters */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
						<Card className="bg-zinc-900/60 border-zinc-800/80">
							<CardHeader>
								<CardTitle className="text-sm flex items-center gap-2 text-zinc-100">
									<Filter className="w-4 h-4 text-emerald-400" />
									<span>Ngưỡng Điểm Lọc (Quality Thresholds)</span>
								</CardTitle>
							</CardHeader>
							<CardContent className="space-y-6">
								{/* Min Fit Score */}
								<div className="space-y-2">
									<div className="flex justify-between text-xs">
										<span className="text-zinc-300">Ngưỡng Fit Score tối thiểu:</span>
										<span className="font-bold text-emerald-400">{minFitScore}/100</span>
									</div>
									<Slider
										value={[minFitScore]}
										onValueChange={(val) => setMinFitScore(val[0])}
										max={100}
										min={0}
										step={5}
									/>
									<p className="text-[11px] text-zinc-500">
										Chỉ lưu các lead đạt độ khớp cao so với ICP doanh nghiệp đã định nghĩa
									</p>
								</div>

								{/* Min Intent Score */}
								<div className="space-y-2">
									<div className="flex justify-between text-xs">
										<span className="text-zinc-300">Ngưỡng Intent Score tối thiểu:</span>
										<span className="font-bold text-amber-400">{minIntentScore}/100</span>
									</div>
									<Slider
										value={[minIntentScore]}
										onValueChange={(val) => setMinIntentScore(val[0])}
										max={100}
										min={0}
										step={5}
									/>
									<p className="text-[11px] text-zinc-500">
										Đánh giá độ nóng và tính cấp thiết của nhu cầu từ nội dung bài đăng
									</p>
								</div>

								{/* Max contacts */}
								<div className="space-y-2">
									<div className="flex justify-between text-xs">
										<span className="text-zinc-300">Số liên hệ tối đa mở khóa / 1 Lead:</span>
										<span className="font-bold text-blue-400">{maxContactsPerLead} người</span>
									</div>
									<Slider
										value={[maxContactsPerLead]}
										onValueChange={(val) => setMaxContactsPerLead(val[0])}
										max={10}
										min={1}
										step={1}
									/>
								</div>
							</CardContent>
						</Card>

						{/* Budget & Compliance Settings */}
						<Card className="bg-zinc-900/60 border-zinc-800/80">
							<CardHeader>
								<CardTitle className="text-sm flex items-center gap-2 text-zinc-100">
									<Coins className="w-4 h-4 text-emerald-400" />
									<span>Mục Tiêu Số Lượng & Dự Toán Chi Phí</span>
								</CardTitle>
							</CardHeader>
							<CardContent className="space-y-4">
								{/* Target Leads */}
								<div>
									<Label className="text-xs text-zinc-300">Mục tiêu số lượng Lead cần quét</Label>
									<Input
										type="number"
										value={expectedLeadsTarget}
										onChange={(e) =>
											setExpectedLeadsTarget(Math.max(10, parseInt(e.target.value, 10) || 0))
										}
										className="mt-1.5 text-xs bg-zinc-950/70 border-zinc-800"
									/>
								</div>

								{/* Compliance & DNC Switch */}
								<div className="p-3.5 rounded-xl bg-zinc-950/60 border border-zinc-800/80 space-y-3">
									<div className="flex items-center justify-between">
										<div className="space-y-0.5">
											<div className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
												<ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
												<span>Tự động loại bỏ danh sách Do-Not-Call (DNC)</span>
											</div>
											<p className="text-[11px] text-zinc-400">
												Tuân thủ Nghị định 91/2020/NĐ-CP & Luật Quảng cáo
											</p>
										</div>
										<Switch checked={excludeDnc} onCheckedChange={setExcludeDnc} />
									</div>

									<div className="flex items-center justify-between pt-2 border-t border-zinc-800/60">
										<div className="space-y-0.5">
											<div className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
												<Zap className="w-3.5 h-3.5 text-amber-400" />
												<span>Tự động giải mã SĐT đã xác thực Zalo</span>
											</div>
											<p className="text-[11px] text-zinc-400">
												Mở khóa số phone hợp lệ ngay khi quét thấy
											</p>
										</div>
										<Switch checked={autoUnlockPhones} onCheckedChange={setAutoUnlockPhones} />
									</div>
								</div>

								{/* Cost Summary Box */}
								<div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-800/40 text-xs space-y-1">
									<div className="flex justify-between text-zinc-300">
										<span>Ước tính chi phí chiến dịch:</span>
										<strong className="text-emerald-400 font-mono text-sm">
											{estimatedCost.toLocaleString("vi-VN")} đ
										</strong>
									</div>
									<p className="text-[10px] text-zinc-400">
										Bao gồm chi phí quét dữ liệu, phân tích AI & mở khóa danh bạ chất lượng cao
									</p>
								</div>
							</CardContent>
						</Card>
					</div>

					{/* Navigation Buttons */}
					<div className="flex justify-between gap-3 pt-4 border-t border-zinc-800">
						<Button
							type="button"
							variant="outline"
							onClick={() => setCurrentStep(1)}
							className="text-xs text-zinc-300 border-zinc-700"
						>
							<ChevronLeft className="w-3.5 h-3.5 mr-1" />
							Quay lại Bước 1
						</Button>
						<Button
							type="button"
							onClick={() => setCurrentStep(3)}
							className="bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold px-6"
						>
							Tiếp tục: Launch & Kích hoạt
							<ArrowRight className="w-3.5 h-3.5 ml-1.5" />
						</Button>
					</div>
				</div>
			)}

			{/* ================= STEP 3: LAUNCH & SCHEDULE ================= */}
			{currentStep === 3 && (
				<div className="space-y-6">
					<div className="grid grid-cols-1 md:grid-cols-12 gap-6">
						{/* Left Form: Name & Schedule Settings */}
						<div className="md:col-span-7 space-y-6">
							<Card className="bg-zinc-900/60 border-zinc-800/80">
								<CardHeader>
									<CardTitle className="text-base flex items-center gap-2 text-zinc-100">
										<Rocket className="w-4 h-4 text-emerald-400" />
										<span>3. Thông Tin & Thiết Lập Lên Lịch</span>
									</CardTitle>
									<CardDescription className="text-xs text-zinc-400">
										Đặt tên chiến dịch và chọn lịch trình chạy tự động
									</CardDescription>
								</CardHeader>
								<CardContent className="space-y-4">
									<div>
										<Label className="text-xs text-zinc-300">Tên chiến dịch</Label>
										<Input
											value={campaignName}
											onChange={(e) => setCampaignName(e.target.value)}
											placeholder="Ví dụ: SDR Outbound Q3 - B2B Fintech"
											className="mt-1.5 text-xs bg-zinc-950/70 border-zinc-800 text-zinc-200"
										/>
									</div>

									<div>
										<Label className="text-xs text-zinc-300">Mô tả / Ghi chú mục tiêu</Label>
										<Textarea
											value={campaignDesc}
											onChange={(e) => setCampaignDesc(e.target.value)}
											rows={2}
											placeholder="Mục tiêu cung cấp 200 leads cho team SDR Hà Nội..."
											className="mt-1.5 text-xs bg-zinc-950/70 border-zinc-800 text-zinc-200"
										/>
									</div>

									{/* Schedule Mode */}
									<div>
										<Label className="text-xs text-zinc-300">Chế độ vận hành</Label>
										<div className="grid grid-cols-2 gap-3 mt-1.5">
											<button
												type="button"
												onClick={() => setScheduleType("once")}
												className={`text-left p-3 rounded-xl border cursor-pointer transition-all ${
													scheduleType === "once"
														? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300"
														: "bg-zinc-950/40 border-zinc-800 text-zinc-400 hover:border-zinc-700"
												}`}
											>
												<div className="flex items-center gap-2 font-bold text-xs">
													<Play className="w-3.5 h-3.5" />
													<span>Chạy một lần ngay (Run Once)</span>
												</div>
												<p className="text-[10px] text-zinc-500 mt-1">
													Quét dữ liệu và kết thúc chu kỳ ngay
												</p>
											</button>

											<button
												type="button"
												onClick={() => setScheduleType("recurring")}
												className={`text-left p-3 rounded-xl border cursor-pointer transition-all ${
													scheduleType === "recurring"
														? "bg-emerald-500/10 border-emerald-500/50 text-emerald-300"
														: "bg-zinc-950/40 border-zinc-800 text-zinc-400 hover:border-zinc-700"
												}`}
											>
												<div className="flex items-center gap-2 font-bold text-xs">
													<Calendar className="w-3.5 h-3.5" />
													<span>Định kỳ tự động (Recurring)</span>
												</div>
												<p className="text-[10px] text-zinc-500 mt-1">
													Lặp lại quét hàng ngày hoặc hàng tuần
												</p>
											</button>
										</div>
									</div>

									{scheduleType === "recurring" && (
										<div>
											<Label className="text-xs text-zinc-300">
												Biểu thức Lịch Cron (Cron Expression)
											</Label>
											<Input
												value={cronExp}
												onChange={(e) => setCronExp(e.target.value)}
												placeholder="0 8 * * 1-5 (Mỗi 8:00 sáng từ thứ 2 - thứ 6)"
												className="mt-1.5 text-xs bg-zinc-950/70 border-zinc-800 font-mono"
											/>
										</div>
									)}

									{/* Export Destination */}
									<div>
										<Label className="text-xs text-zinc-300">
											Đích đến dữ liệu Leads sau khi phân tích
										</Label>
										<select
											value={exportDestination}
											onChange={(e) =>
												setExportDestination(
													e.target.value as "workspace" | "crm" | "lark" | "sheets"
												)
											}
											className="w-full mt-1.5 px-3 py-2 text-xs rounded-lg bg-zinc-950/70 border border-zinc-800 text-zinc-200 focus:ring-1 focus:ring-emerald-500"
										>
											<option value="workspace">Nowing SDR Lead Workbench (Mặc định)</option>
											<option value="crm">Đẩy sang CRM (HubSpot / Salesforce / Lark Base)</option>
											<option value="lark">Bắn thông báo qua Lark Webhook</option>
											<option value="sheets">Tự động đồng bộ Google Sheets</option>
										</select>
									</div>
								</CardContent>
							</Card>
						</div>

						{/* Right Column: Campaign Preview Summary */}
						<div className="md:col-span-5">
							<Card className="bg-zinc-900/80 border-emerald-500/30 sticky top-6 shadow-2xl">
								<CardHeader className="pb-3 border-b border-zinc-800">
									<CardTitle className="text-sm font-bold text-zinc-100 flex items-center justify-between">
										<span>Tóm Tắt Cấu Hình Chiến Dịch</span>
										<Badge
											variant="outline"
											className="bg-emerald-500/10 text-emerald-400 border-emerald-500/30 text-[10px]"
										>
											Ready to Launch
										</Badge>
									</CardTitle>
								</CardHeader>
								<CardContent className="space-y-3 pt-4 text-xs">
									<div className="space-y-1">
										<span className="text-zinc-500 text-[11px]">Tên chiến dịch:</span>
										<p className="font-semibold text-zinc-200">{campaignName || "Chưa đặt tên"}</p>
									</div>

									<div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-800/60">
										<div>
											<span className="text-zinc-500 text-[11px]">Mẫu ngành:</span>
											<p className="font-medium text-emerald-400">
												{VERTICAL_PRESETS[selectedTemplate].label}
											</p>
										</div>
										<div>
											<span className="text-zinc-500 text-[11px]">Mục tiêu số Lead:</span>
											<p className="font-bold text-zinc-200">{expectedLeadsTarget} leads</p>
										</div>
									</div>

									<div className="pt-2 border-t border-zinc-800/60">
										<span className="text-zinc-500 text-[11px]">
											Nguồn quét ({selectedSources.length}):
										</span>
										<div className="flex flex-wrap gap-1 mt-1">
											{selectedSources.map((s) => (
												<Badge
													key={s}
													variant="secondary"
													className="text-[10px] bg-zinc-800 text-zinc-300"
												>
													{s}
												</Badge>
											))}
										</div>
									</div>

									<div className="grid grid-cols-2 gap-2 pt-2 border-t border-zinc-800/60">
										<div>
											<span className="text-zinc-500 text-[11px]">Ngưỡng Fit Score:</span>
											<p className="font-bold text-emerald-400">{minFitScore}/100</p>
										</div>
										<div>
											<span className="text-zinc-500 text-[11px]">Ngưỡng Intent Score:</span>
											<p className="font-bold text-amber-400">{minIntentScore}/100</p>
										</div>
									</div>

									<div className="pt-2 border-t border-zinc-800/60">
										<span className="text-zinc-500 text-[11px]">Loại trừ DNC:</span>
										<p className="text-zinc-300 font-medium">
											{excludeDnc ? "✅ Bật (Loại trừ số cấm)" : "❌ Tắt"}
										</p>
									</div>

									<div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-800/40 mt-4">
										<div className="flex justify-between items-center text-xs">
											<span className="text-zinc-300">Tổng ngân sách dự toán:</span>
											<span className="font-mono font-bold text-emerald-400 text-sm">
												{estimatedCost.toLocaleString("vi-VN")} đ
											</span>
										</div>
									</div>
								</CardContent>
								<CardFooter className="flex flex-col gap-2 pt-2 border-t border-zinc-800">
									<Button
										type="button"
										disabled={isSubmitting}
										onClick={() => handleSaveCampaign(true)}
										className="w-full bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold py-2.5 shadow-lg shadow-emerald-500/20"
									>
										{isSubmitting ? (
											<>
												<Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
												Đang khởi chạy...
											</>
										) : (
											<>
												<Rocket className="w-3.5 h-3.5 mr-1.5" />
												Kích Hoạt Chiến Dịch Ngay (Launch)
											</>
										)}
									</Button>
									<Button
										type="button"
										variant="ghost"
										disabled={isSubmitting}
										onClick={() => handleSaveCampaign(false)}
										className="w-full text-xs text-zinc-400 hover:text-zinc-200"
									>
										Lưu bản nháp (Save Draft)
									</Button>
								</CardFooter>
							</Card>
						</div>
					</div>

					{/* Navigation Footer */}
					<div className="flex justify-start pt-4 border-t border-zinc-800">
						<Button
							type="button"
							variant="outline"
							onClick={() => setCurrentStep(2)}
							className="text-xs text-zinc-300 border-zinc-700"
						>
							<ChevronLeft className="w-3.5 h-3.5 mr-1" />
							Quay lại Bước 2
						</Button>
					</div>
				</div>
			)}
		</div>
	);
};
