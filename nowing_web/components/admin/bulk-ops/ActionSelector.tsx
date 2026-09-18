"use client";

import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { ACTION_METADATA, type BulkAction } from "@/contracts/types/admin-bulk-ops.types";
import { useTranslations } from "next-intl";

interface ActionSelectorProps {
	value: BulkAction | "";
	onChange: (action: BulkAction) => void;
	isSuperadmin?: boolean;
	disabled?: boolean;
}

export function ActionSelector({
	value,
	onChange,
	isSuperadmin = true,
	disabled = false,
}: ActionSelectorProps) {
	const t = useTranslations("bulkOps");

	const actionLabels: Record<BulkAction, { label: string; desc: string }> = {
		archive_inactive_workspaces: {
			label: t("action_archive_workspaces_label"),
			desc: t("action_archive_workspaces_desc"),
		},
		rotate_api_keys: {
			label: t("action_rotate_keys_label"),
			desc: t("action_rotate_keys_desc"),
		},
		assign_role: {
			label: t("action_assign_role_label"),
			desc: t("action_assign_role_desc"),
		},
		delete_source_type_memories: {
			label: t("action_delete_memories_label"),
			desc: t("action_delete_memories_desc"),
		},
		apply_tier: {
			label: t("action_apply_tier_label"),
			desc: t("action_apply_tier_desc"),
		},
		revoke_membership: {
			label: t("action_revoke_membership_label"),
			desc: t("action_revoke_membership_desc"),
		},
	};

	const actions = (Object.keys(ACTION_METADATA) as BulkAction[]).filter((action) => {
		if (!isSuperadmin && ACTION_METADATA[action].superadminOnly) {
			return false;
		}
		return true;
	});

	return (
		<div className="space-y-2">
			<div className="flex items-center justify-between">
				<Label htmlFor="bulk-action-select" className="text-sm font-medium">
					{t("select_action")}
				</Label>
				{value && ACTION_METADATA[value]?.isHighRisk && (
					<Badge variant="destructive" className="text-xs">
						{t("high_risk_badge")}
					</Badge>
				)}
			</div>
			<Select
				value={value}
				onValueChange={(val) => onChange(val as BulkAction)}
				disabled={disabled}
			>
				<SelectTrigger id="bulk-action-select" className="w-full">
					<SelectValue placeholder={t("choose_action_placeholder")} />
				</SelectTrigger>
				<SelectContent>
					{actions.map((action) => {
						const meta = ACTION_METADATA[action];
						const info = actionLabels[action];
						return (
							<SelectItem key={action} value={action}>
								<div className="flex flex-col py-1 text-left">
									<div className="flex items-center gap-2">
										<span className="font-semibold">{info.label}</span>
										{meta.isHighRisk && (
											<span className="text-[10px] text-red-500 font-bold uppercase tracking-wider">
												MFA
											</span>
										)}
									</div>
									<span className="text-xs text-muted-foreground">{info.desc}</span>
								</div>
							</SelectItem>
						);
					})}
				</SelectContent>
			</Select>
		</div>
	);
}
