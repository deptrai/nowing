"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";

import type {
	CampaignCreateInput,
	CampaignIntent,
	IcpConfig,
	IcpVerticalTemplate,
	LaunchConfig,
	SourceBudgetConfig,
} from "@/contracts/types/campaign.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";

import { VERTICAL_PRESETS } from "./constants";
import type { CampaignBuilderProps, UseCampaignBuilderReturn } from "./types";

export function useCampaignBuilder({
	workspaceId,
	onCampaignCreated,
}: CampaignBuilderProps): UseCampaignBuilderReturn {
	const [currentStep, setCurrentStep] = useState<1 | 2 | 3>(1);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [isAnalyzingIcp, setIsAnalyzingIcp] = useState(false);

	const [campaignName, setCampaignName] = useState("Chiến dịch tìm kiếm Lead ICP Q3");
	const [campaignDesc, setCampaignDesc] = useState(
		"Tự động quét tín hiệu thị trường và chấm điểm Fit Score tự động"
	);

	const [selectedTemplate, setSelectedTemplate] = useState<IcpVerticalTemplate>("b2b_saas");
	const [targetIndustries, setTargetIndustries] = useState<string[]>(
		VERTICAL_PRESETS.b2b_saas.industries
	);
	const [industryInput, setIndustryInput] = useState("");
	const [locations, setLocations] = useState<string[]>(VERTICAL_PRESETS.b2b_saas.locations);
	const [locationInput, setLocationInput] = useState("");
	const [companySize, setCompanySize] = useState(VERTICAL_PRESETS.b2b_saas.companySize);
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
	const [customInstructions, setCustomInstructions] = useState("");

	const [selectedSources, setSelectedSources] = useState<string[]>(
		VERTICAL_PRESETS.b2b_saas.sources
	);
	const [expectedLeadsTarget, setExpectedLeadsTarget] = useState<number>(150);
	const [minFitScore, setMinFitScore] = useState<number>(70);
	const [minIntentScore, setMinIntentScore] = useState<number>(60);
	const [maxContactsPerLead, setMaxContactsPerLead] = useState<number>(3);
	const [excludeDnc, setExcludeDnc] = useState<boolean>(true);
	const [autoUnlockPhones, setAutoUnlockPhones] = useState<boolean>(false);
	const [maxDailySpend] = useState<number>(500_000);

	const [scheduleType, setScheduleType] = useState<LaunchConfig["schedule_type"]>("once");
	const [cronExp, setCronExp] = useState("0 8 * * 1-5");
	const [autoStart] = useState(true);
	const [exportDestination, setExportDestination] = useState<
		"workspace" | "crm" | "lark" | "sheets"
	>("workspace");

	const estimatedCost = useMemo(() => {
		const costPerLead = autoUnlockPhones ? 5000 : 1500;
		return expectedLeadsTarget * costPerLead;
	}, [expectedLeadsTarget, autoUnlockPhones]);

	const selectTemplate = (templateKey: IcpVerticalTemplate) => {
		setSelectedTemplate(templateKey);
		const preset = VERTICAL_PRESETS[templateKey];
		setTargetIndustries(preset.industries);
		setLocations(preset.locations);
		setCompanySize(preset.companySize);
		setTechStack(preset.techStack);
		setSelectedIntents(preset.intents);
		setSelectedSources(preset.sources);
	};

	const addItem = (
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

	const removeItem = (index: number, list: string[], setter: (val: string[]) => void) => {
		setter(list.filter((_, i) => i !== index));
	};

	const addIndustry = () =>
		addItem(industryInput, targetIndustries, setTargetIndustries, setIndustryInput);
	const removeIndustry = (index: number) =>
		removeItem(index, targetIndustries, setTargetIndustries);

	const addLocation = () => addItem(locationInput, locations, setLocations, setLocationInput);
	const removeLocation = (index: number) => removeItem(index, locations, setLocations);

	const addTech = () => addItem(techInput, techStack, setTechStack, setTechInput);
	const removeTech = (index: number) => removeItem(index, techStack, setTechStack);

	const addNegativeKeyword = () =>
		addItem(negativeInput, negativeKeywords, setNegativeKeywords, setNegativeInput);
	const removeNegativeKeyword = (index: number) =>
		removeItem(index, negativeKeywords, setNegativeKeywords);

	const toggleIntent = (intent: CampaignIntent) => {
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

	const toggleSource = (sourceId: string) => {
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

	return {
		currentStep,
		isSubmitting,
		isAnalyzingIcp,
		campaignName,
		campaignDesc,
		selectedTemplate,
		targetIndustries,
		industryInput,
		locations,
		locationInput,
		companySize,
		techStack,
		techInput,
		selectedIntents,
		negativeKeywords,
		negativeInput,
		reverseIcpUrl,
		customInstructions,
		selectedSources,
		expectedLeadsTarget,
		minFitScore,
		minIntentScore,
		maxContactsPerLead,
		excludeDnc,
		autoUnlockPhones,
		maxDailySpend,
		scheduleType,
		cronExp,
		autoStart,
		exportDestination,
		estimatedCost,

		setCurrentStep,
		setCampaignName,
		setCampaignDesc,

		selectTemplate,
		addIndustry,
		removeIndustry,
		setIndustryInput,

		addLocation,
		removeLocation,
		setLocationInput,

		setCompanySize,

		addTech,
		removeTech,
		setTechInput,

		toggleIntent,

		addNegativeKeyword,
		removeNegativeKeyword,
		setNegativeInput,

		setReverseIcpUrl,
		setCustomInstructions,

		toggleSource,

		setExpectedLeadsTarget,
		setMinFitScore,
		setMinIntentScore,
		setMaxContactsPerLead,
		setExcludeDnc,
		setAutoUnlockPhones,

		setScheduleType,
		setCronExp,
		setExportDestination,

		handleAnalyzeReverseIcp,
		handleSaveCampaign,
	};
}
