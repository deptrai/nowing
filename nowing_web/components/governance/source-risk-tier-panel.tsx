"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import type { RiskTier, SourceRiskTier, SourceRiskTierUpdate } from "@/contracts/types/governance.types";
import { MemorySourceType } from "@/contracts/types/governance.types";
import { governanceApiService } from "@/lib/apis/governance-api.service";
import { toast } from "sonner";

interface SourceRiskTierPanelProps {
	workspaceId: number;
	tiers: SourceRiskTier[];
	canEdit: boolean;
	onChanged: () => void;
	className?: string;
}

const allMemorySourceTypes: string[] = [
	"document",
	"chat_message",
	"scraper_run",
	"manual",
	"unknown",
	"signal",
	"lead",
	"lead_score",
	"enrichment",
	"crm_connection",
	"crm_sync",
	"sequence_event",
	"outcome_event",
];

function riskBadge(risk: RiskTier) {
	switch (risk) {
		case "low":
			return <Badge variant="secondary">Low</Badge>;
		case "medium":
			return <Badge variant="default">Medium</Badge>;
		case "high":
			return <Badge variant="destructive">High</Badge>;
	}
}

export function SourceRiskTierPanel({
	workspaceId,
	tiers,
	canEdit,
	onChanged,
	className,
}: SourceRiskTierPanelProps) {
	const t = useTranslations("governance");
	const tCommon = useTranslations("common");
	const [editing, setEditing] = useState<SourceRiskTier | null>(null);
	const [confirmHigh, setConfirmHigh] = useState<SourceRiskTierUpdate | null>(null);
	const [saving, setSaving] = useState(false);

	const tierMap = useMemo(() => {
		const map = new Map<string, SourceRiskTier>();
		for (const tier of tiers) {
			map.set(tier.source_type, tier);
		}
		return map;
	}, [tiers]);

	const handleUpsert = useCallback(
		async (payload: SourceRiskTierUpdate) => {
			if (!canEdit) return;
			if (payload.risk_tier === "high") {
				setConfirmHigh(payload);
				return;
			}

			setSaving(true);
			try {
				await governanceApiService.upsertSourceRiskTier(workspaceId, payload);
				onChanged();
				toast.success(t("source_tiers.saved"));
			} catch (error) {
				console.error("Error saving source risk tier:", error);
				toast.error(error instanceof Error ? error.message : t("errors.save_failed"));
			} finally {
				setSaving(false);
				setEditing(null);
			}
		},
		[canEdit, workspaceId, onChanged, t]
	);

	const confirmHighRisk = useCallback(
		async (accepted: boolean) => {
			if (!accepted || !confirmHigh) {
				setConfirmHigh(null);
				return;
			}

			setSaving(true);
			try {
				await governanceApiService.upsertSourceRiskTier(workspaceId, confirmHigh);
				onChanged();
				toast.success(t("source_tiers.saved"));
			} catch (error) {
				console.error("Error saving source risk tier:", error);
				toast.error(error instanceof Error ? error.message : t("errors.save_failed"));
			} finally {
				setSaving(false);
				setConfirmHigh(null);
				setEditing(null);
			}
		},
		[confirmHigh, workspaceId, onChanged, t]
	);

	return (
		<section aria-label={t("source_tiers.title")} className={cn("space-y-4", className)}>
			<div className="space-y-1">
				<h2 className="text-lg font-semibold">{t("source_tiers.title")}</h2>
				<p className="text-sm text-muted-foreground">{t("source_tiers.description")}</p>
			</div>

			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>{t("source_tiers.source_type")}</TableHead>
						<TableHead>{t("source_tiers.risk_tier")}</TableHead>
						<TableHead>{t("source_tiers.recommended_retention")}</TableHead>
						<TableHead>{t("source_tiers.notes")}</TableHead>
						<TableHead className="w-24">{tCommon("actions")}</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{allMemorySourceTypes.map((sourceType) => {
						const tier = tierMap.get(sourceType);
						return (
							<TableRow key={sourceType}>
								<TableCell className="font-medium">{sourceType}</TableCell>
								<TableCell>{tier ? riskBadge(tier.risk_tier as RiskTier) : "—"}</TableCell>
								<TableCell>
									{tier?.recommended_retention_days
										? `${tier.recommended_retention_days} days`
										: "—"}
								</TableCell>
								<TableCell className="max-w-sm truncate">
									{tier?.notes || "—"}
								</TableCell>
								<TableCell>
									<Button
										variant="ghost"
										size="sm"
										disabled={!canEdit}
										onClick={() =>
											setEditing(
												tier ?? {
													source_type: sourceType,
													risk_tier: "low",
													recommended_retention_days: null,
													notes: null,
												}
											)
										}
									>
										{tCommon("edit")}
									</Button>
								</TableCell>
							</TableRow>
						);
					})}
				</TableBody>
			</Table>

			<Dialog open={!!editing} onOpenChange={(open) => !open && setEditing(null)}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle>{t("source_tiers.edit_title")}</DialogTitle>
						<DialogDescription>
							{t("source_tiers.edit_description", { source: editing?.source_type ?? "" })}
						</DialogDescription>
					</DialogHeader>
					{editing && (
						<EditTierForm
							tier={editing}
							saving={saving}
							onCancel={() => setEditing(null)}
							onSave={handleUpsert}
						/>
					)}
				</DialogContent>
			</Dialog>

			<Dialog open={!!confirmHigh} onOpenChange={(open) => !open && confirmHighRisk(false)}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle className="flex items-center gap-2">
							<AlertTriangle className="h-5 w-5 text-destructive" />
							{t("source_tiers.high_risk_title")}
						</DialogTitle>
						<DialogDescription>
							{t("source_tiers.high_risk_description", {
								source: confirmHigh?.source_type ?? "",
							})}
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="gap-2">
						<Button variant="outline" onClick={() => confirmHighRisk(false)}>
							{tCommon("cancel")}
						</Button>
						<Button
							variant="destructive"
							disabled={saving}
							onClick={() => confirmHighRisk(true)}
						>
							{saving ? tCommon("save") : t("source_tiers.confirm_high_risk")}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</section>
	);
}

function EditTierForm({
	tier,
	saving,
	onCancel,
	onSave,
}: {
	tier: SourceRiskTier;
	saving: boolean;
	onCancel: () => void;
	onSave: (payload: SourceRiskTierUpdate) => void;
}) {
	const t = useTranslations("governance");
	const tCommon = useTranslations("common");
	const [riskTier, setRiskTier] = useState<RiskTier>(tier.risk_tier as RiskTier);
	const [days, setDays] = useState(String(tier.recommended_retention_days ?? ""));
	const [notes, setNotes] = useState(tier.notes ?? "");

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		onSave({
			source_type: tier.source_type,
			risk_tier: riskTier,
			recommended_retention_days: days.trim() === "" ? null : Number(days),
			notes: notes.trim() === "" ? null : notes,
		});
	};

	return (
		<form onSubmit={handleSubmit} className="space-y-4">
			<div className="space-y-2">
				<Label htmlFor="risk-tier">{t("source_tiers.risk_tier")}</Label>
				<select
					id="risk-tier"
					value={riskTier}
					onChange={(e) => setRiskTier(e.target.value as RiskTier)}
					className={cn(
						"flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
					)}
				>
					<option value="low">Low</option>
					<option value="medium">Medium</option>
					<option value="high">High</option>
				</select>
			</div>

			<div className="space-y-2">
				<Label htmlFor="recommended-days">{t("source_tiers.recommended_retention")}</Label>
				<Input
					id="recommended-days"
					type="number"
					value={days}
					onChange={(e) => setDays(e.target.value)}
					placeholder="180"
				/>
			</div>

			<div className="space-y-2">
				<Label htmlFor="tier-notes">{t("source_tiers.notes")}</Label>
				<Input
					id="tier-notes"
					value={notes}
					onChange={(e) => setNotes(e.target.value)}
					placeholder={t("source_tiers.notes_placeholder")}
				/>
			</div>

			<DialogFooter className="gap-2">
				<Button type="button" variant="outline" onClick={onCancel}>
					{tCommon("cancel")}
				</Button>
				<Button type="submit" disabled={saving}>
					{saving ? tCommon("save") : tCommon("save")}
				</Button>
			</DialogFooter>
		</form>
	);
}
