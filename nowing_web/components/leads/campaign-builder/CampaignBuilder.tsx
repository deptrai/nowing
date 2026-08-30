"use client";

import type { Campaign } from "@/contracts/types/campaign.types";
import { IcpBuilderStep } from "./steps/IcpBuilderStep";
import { LaunchScheduleStep } from "./steps/LaunchScheduleStep";
import { SourceBudgetStep } from "./steps/SourceBudgetStep";
import { useCampaignBuilder } from "./use-campaign-builder";
import { WizardStepsHeader } from "./WizardStepsHeader";

export interface CampaignBuilderProps {
	workspaceId: string | number;
	onCampaignCreated?: (campaign: Campaign) => void;
	onCancel?: () => void;
}

export function CampaignBuilder({
	workspaceId,
	onCampaignCreated,
	onCancel,
}: CampaignBuilderProps) {
	const builder = useCampaignBuilder({ workspaceId, onCampaignCreated });

	return (
		<div className="space-y-6 max-w-6xl mx-auto pb-12">
			<WizardStepsHeader currentStep={builder.currentStep} onStepChange={builder.setCurrentStep} />

			{builder.currentStep === 1 && <IcpBuilderStep builder={builder} onCancel={onCancel} />}
			{builder.currentStep === 2 && <SourceBudgetStep builder={builder} />}
			{builder.currentStep === 3 && <LaunchScheduleStep builder={builder} />}
		</div>
	);
}
