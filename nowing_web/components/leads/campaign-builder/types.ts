import type {
	Campaign,
	CampaignCreateInput,
	CampaignIntent,
	CampaignPlanResponse,
	IcpVerticalTemplate,
	LaunchConfig,
} from "@/contracts/types/campaign.types";
import type { LocationProfile } from "@/contracts/types/leads.types";

export interface CampaignBuilderProps {
	workspaceId: string | number;
	onCampaignCreated?: (campaign: Campaign) => void;
	onCancel?: () => void;
}

export interface CampaignBuilderState {
	currentStep: 1 | 2 | 3;
	isSubmitting: boolean;
	isAnalyzingIcp: boolean;

	campaignName: string;
	campaignDesc: string;

	selectedTemplate: IcpVerticalTemplate;
	targetIndustries: string[];
	industryInput: string;
	locations: string[];
	locationInput: string;
	companySize: string;
	techStack: string[];
	techInput: string;
	selectedIntents: CampaignIntent[];
	negativeKeywords: string[];
	negativeInput: string;
	reverseIcpUrl: string;
	customInstructions: string;

	selectedSources: string[];
	expectedLeadsTarget: number;
	minFitScore: number;
	minIntentScore: number;
	maxContactsPerLead: number;
	excludeDnc: boolean;
	autoUnlockPhones: boolean;
	maxDailySpend: number;

	locationProfile: LocationProfile | null;
	activePlan: CampaignPlanResponse | null;
	isPlanning: boolean;

	scheduleType: LaunchConfig["schedule_type"];
	cronExp: string;
	autoStart: boolean;
	exportDestination: "workspace" | "crm" | "lark" | "sheets";
}

export interface UseCampaignBuilderReturn extends CampaignBuilderState {
	setCurrentStep: (step: 1 | 2 | 3) => void;
	setCampaignName: (value: string) => void;
	setCampaignDesc: (value: string) => void;

	selectTemplate: (template: IcpVerticalTemplate) => void;
	addIndustry: () => void;
	removeIndustry: (index: number) => void;
	setIndustryInput: (value: string) => void;

	addLocation: () => void;
	removeLocation: (index: number) => void;
	setLocationInput: (value: string) => void;

	setCompanySize: (value: string) => void;

	addTech: () => void;
	removeTech: (index: number) => void;
	setTechInput: (value: string) => void;

	toggleIntent: (intent: CampaignIntent) => void;

	addNegativeKeyword: () => void;
	removeNegativeKeyword: (index: number) => void;
	setNegativeInput: (value: string) => void;

	setReverseIcpUrl: (value: string) => void;
	setCustomInstructions: (value: string) => void;

	toggleSource: (sourceId: string) => void;

	setExpectedLeadsTarget: (value: number) => void;
	setMinFitScore: (value: number) => void;
	setMinIntentScore: (value: number) => void;
	setMaxContactsPerLead: (value: number) => void;
	setExcludeDnc: (value: boolean) => void;
	setAutoUnlockPhones: (value: boolean) => void;

	setLocationProfile: (value: LocationProfile | null) => void;
	setActivePlan: (value: CampaignPlanResponse | null) => void;
	setActivePlanSpec: (value: CampaignCreateInput | null) => void;
	setActiveCampaignPlan: (value: CampaignPlanResponse | null) => void;

	setScheduleType: (value: LaunchConfig["schedule_type"]) => void;
	setCronExp: (value: string) => void;
	setExportDestination: (value: CampaignBuilderState["exportDestination"]) => void;

	estimatedCost: number;

	buildPlanSpec: () => CampaignCreateInput;
	handleAnalyzeReverseIcp: () => Promise<void>;
	handleGetPlan: () => Promise<void>;
	handleSmokeTest: () => Promise<void>;
	handleLaunchCampaign: () => Promise<void>;
	handleSaveCampaign: (andLaunch?: boolean) => Promise<void>;
}
