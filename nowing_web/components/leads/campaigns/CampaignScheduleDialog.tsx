"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { Campaign, CampaignUpdateInput } from "@/contracts/types/campaign.types";
import { leadsApiService } from "@/lib/apis/leads-api.service";
import { AppError } from "@/lib/error";

// Khớp _USER_SETTABLE_FREQUENCIES backend (campaign_routes.py).
const FREQUENCIES = ["once", "hourly", "daily", "weekly", "monthly", "custom"] as const;
type Frequency = (typeof FREQUENCIES)[number];

const toFrequency = (v: string | null | undefined): Frequency =>
	(FREQUENCIES as readonly string[]).includes(v ?? "") ? (v as Frequency) : "daily";

export function CampaignScheduleDialog({
	workspaceId,
	campaign,
	open,
	onOpenChange,
	onSaved,
}: {
	workspaceId: number | string;
	campaign: Campaign;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	onSaved: () => void;
}) {
	const t = useTranslations("leads");
	const [frequency, setFrequency] = useState<Frequency>(() =>
		toFrequency(campaign.schedule_frequency)
	);
	const [cron, setCron] = useState(campaign.schedule_cron ?? "");
	const [maxRuns, setMaxRuns] = useState(
		campaign.max_runs != null ? String(campaign.max_runs) : ""
	);
	const [saving, setSaving] = useState(false);

	// Reset form về state campaign mỗi lần mở dialog.
	useEffect(() => {
		if (!open) return;
		setFrequency(toFrequency(campaign.schedule_frequency));
		setCron(campaign.schedule_cron ?? "");
		setMaxRuns(campaign.max_runs != null ? String(campaign.max_runs) : "");
	}, [open, campaign]);

	const handleSave = async () => {
		const body: CampaignUpdateInput = {
			schedule_frequency: frequency,
			schedule_cron: frequency === "custom" ? cron.trim() || null : null,
			max_runs: maxRuns.trim() ? Number.parseInt(maxRuns, 10) : null,
		};
		// 'once' chỉ clear schedule — set status='scheduled' sẽ 422 (no next_run).
		if (frequency !== "once") {
			body.status = "scheduled";
		}
		try {
			setSaving(true);
			await leadsApiService.updateCampaign(workspaceId, campaign.id, body);
			toast.success(t("campaign_schedule_saved"));
			onOpenChange(false);
			onSaved();
		} catch (err) {
			// 409/422/429: AppError.message đã chứa `detail` từ response body.
			toast.error(
				err instanceof AppError && err.message ? err.message : t("campaign_actions_error")
			);
		} finally {
			setSaving(false);
		}
	};

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{t("campaign_schedule_title")}</DialogTitle>
					<DialogDescription>{t("campaign_schedule_desc")}</DialogDescription>
				</DialogHeader>
				<div className="space-y-4 py-2">
					<div className="space-y-1.5">
						<span className="text-sm font-medium">{t("campaign_schedule_frequency")}</span>
						<Select value={frequency} onValueChange={(v) => setFrequency(v as Frequency)}>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{FREQUENCIES.map((f) => (
									<SelectItem key={f} value={f}>
										{t(`campaign_schedule_freq_${f}`)}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>
					{frequency === "custom" && (
						<div className="space-y-1.5">
							<span className="text-sm font-medium">{t("campaign_schedule_cron")}</span>
							<Input
								value={cron}
								onChange={(e) => setCron(e.target.value)}
								placeholder="0 9 * * 1"
							/>
							<p className="text-xs text-muted-foreground">{t("campaign_schedule_cron_hint")}</p>
						</div>
					)}
					<div className="space-y-1.5">
						<span className="text-sm font-medium">{t("campaign_schedule_max_runs")}</span>
						<Input
							type="number"
							min={1}
							value={maxRuns}
							onChange={(e) => setMaxRuns(e.target.value)}
							placeholder={t("campaign_schedule_max_runs_hint")}
						/>
					</div>
				</div>
				<DialogFooter>
					<Button variant="outline" onClick={() => onOpenChange(false)}>
						{t("campaign_schedule_cancel")}
					</Button>
					<Button
						onClick={handleSave}
						disabled={saving || (frequency === "custom" && !cron.trim())}
					>
						{saving ? t("campaign_schedule_saving") : t("campaign_schedule_save")}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
