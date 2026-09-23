"use client";

import { useAtom } from "jotai";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
	activeCampaignPlanAtom,
	activePlanSpecAtom,
	activeSmokeTestResultAtom,
	previousLocationProfileAtom,
	smokeTestHistoryAtom,
} from "@/atoms/leads/leads-canvas.atoms";

import type {
	CampaignCreateInput,
	CampaignIntent,
	CampaignPlanResponse,
	IcpConfig,
	IcpVerticalTemplate,
	LaunchConfig,
	SourceBudgetConfig,
} from "@/contracts/types/campaign.types";
import type { LocationProfile } from "@/contracts/types/leads.types";
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

	const [locationProfile, setLocationProfile] = useState<LocationProfile | null>(null);
	const [activePlan, setActivePlan] = useState<CampaignPlanResponse | null>(null);
	const [isPlanning, setIsPlanning] = useState(false);

	// Right-Canvas mirror sync (Story 26.27)
	const [, setActivePlanSpec] = useAtom(activePlanSpecAtom);
	const [, setActiveCampaignPlan] = useAtom(activeCampaignPlanAtom);

	// Smoke test feedback loop state (Story 26.29)
	const [smokeTestHistory, setSmokeTestHistory] = useAtom(smokeTestHistoryAtom);
	const [activeSmokeTestResult, setActiveSmokeTestResult] = useAtom(activeSmokeTestResultAtom);
	const [previousLocationProfile, setPreviousLocationProfile] = useAtom(
		previousLocationProfileAtom
	);
	const [locationRefineOpen, setLocationRefineOpen] = useState(false);

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

	const buildPlanSpec = (): CampaignCreateInput => {
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

		return {
			name: campaignName,
			description: campaignDesc || null,
			workspace_id: Number(workspaceId),
			icp_config: {
				...icpConfig,
				location_profile: locationProfile || null,
			},
			source_budget_config: sourceBudgetConfig,
			launch_config: launchConfig,
		};
	};

	const handleGetPlan = async () => {
		if (selectedSources.length === 0) {
			toast.error("Phải chọn ít nhất 1 nguồn dữ liệu");
			return;
		}
		try {
			setIsPlanning(true);
			const spec = buildPlanSpec();
			setActivePlanSpec(spec);
			const plan = await leadsApiService.planCampaign(workspaceId, spec);
			setActivePlan(plan);
			setActiveCampaignPlan(plan);
			toast.success("Đã tạo bản tổng quan kế hoạch (Pre-Flight Plan)");
		} catch (_err) {
			toast.error("Không thể tạo kế hoạch. Vui lòng kiểm tra cấu hình nguồn và địa bàn.");
		} finally {
			setIsPlanning(false);
		}
	};

	const handleSmokeTest = async () => {
		if (selectedSources.length === 0) {
			toast.error("Phải chọn ít nhất 1 nguồn dữ liệu");
			return;
		}
		try {
			setIsPlanning(true);
			const spec = buildPlanSpec();
			spec.source_budget_config.expected_leads_target = 5;
			spec.source_budget_config.max_contacts_per_lead = 1;
			// Keep the location profile from the PREVIOUS run so the diff card
			// compares against the last smoke test, not the current one.
			const priorRunProfile = activeSmokeTestResult?.location_profile ?? locationProfile;
			const currentRunProfile = locationProfile;

			const result = await leadsApiService.executeCampaign(workspaceId, spec, false);
			const run = {
				run_id: crypto.randomUUID(),
				executed_at: new Date().toISOString(),
				result,
				location_profile: currentRunProfile,
				spec,
			};
			setActiveSmokeTestResult(run);
			setSmokeTestHistory((prev) => [...prev, run]);
			setPreviousLocationProfile(priorRunProfile);

			if (!activePlan) {
				return;
			}
			const smokePlan: CampaignPlanResponse = {
				...activePlan,
				estimated_reachable_leads: result.total_discovered,
				estimated_cost_vnd: result.total_discovered * (autoUnlockPhones ? 5000 : 1500),
				estimated_cost_micros: result.total_discovered * (autoUnlockPhones ? 5000 : 1500) * 40,
			};
			setActivePlan(smokePlan);
			setActiveCampaignPlan(smokePlan);
			toast.success(`Chạy thử xong: tìm thấy ${result.total_discovered} lead`);
		} catch (_err) {
			toast.error("Không thể chạy thử. Vui lòng kiểm tra cấu hình.");
		} finally {
			setIsPlanning(false);
		}
	};

	const handleRefineLocation = (action: "narrow" | "expand" | "switch-source" | "custom") => {
		if (action === "custom" || action === "narrow" || action === "expand") {
			setLocationRefineOpen(true);
		}
		if (action === "switch-source") {
			setCurrentStep(2);
		}
		if (action === "expand" && locationProfile) {
			// Quick expand: drop district/ward filters to search the entire province
			setLocationProfile({
				...locationProfile,
				district_codes: [],
				district_names: [],
				ward_codes: [],
				ward_names: [],
				location_text: locationProfile.province_name || locationProfile.province_code,
			});
		}
	};

	const handleLaunchCampaign = async () => {
		if (selectedSources.length === 0) {
			toast.error("Phải chọn ít nhất 1 nguồn dữ liệu");
			return;
		}
		try {
			setIsSubmitting(true);
			const spec = buildPlanSpec();

			// AC-5 dedup: exclude identities already returned by the approved smoke test
			if (activeSmokeTestResult?.result?.leads?.length) {
				spec.excluded_identities = activeSmokeTestResult.result.leads
					.map((lead) => {
						if (lead.phone) return lead.phone;
						if (lead.domain) return lead.domain;
						if (lead.email) return lead.email;
						return undefined;
					})
					.filter((value): value is string => Boolean(value));
			}

			const result = await leadsApiService.executeCampaign(workspaceId, spec, true);
			toast.success(`Đã chạy chiến dịch: tìm thấy ${result.total_discovered} lead`);
		} catch (_err) {
			toast.error("Không thể chạy chiến dịch. Vui lòng thử lại.");
		} finally {
			setIsSubmitting(false);
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
			const payload = buildPlanSpec();

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

		locationProfile,
		activePlan,
		isPlanning,
		workspaceId,

		smokeTestResult: activeSmokeTestResult?.result ?? null,
		smokeTestHistory,
		activeSmokeTestResult,
		locationRefineOpen,
		previousLocationProfile,

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

		setLocationProfile,
		setActivePlan,
		setActivePlanSpec,
		setActiveCampaignPlan,

		setScheduleType,
		setCronExp,
		setExportDestination,

		buildPlanSpec,
		handleAnalyzeReverseIcp,
		handleGetPlan,
		handleSmokeTest,
		handleRefineLocation,
		handleLaunchCampaign,
		handleSaveCampaign,
		setLocationRefineOpen,
	};
}
