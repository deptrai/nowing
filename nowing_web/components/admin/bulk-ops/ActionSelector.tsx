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

interface ActionSelectorProps {
	value: BulkAction | "";
	onChange: (action: BulkAction) => void;
	isSuperadmin?: boolean;
	disabled?: boolean;
}

const ACTION_LABELS: Record<BulkAction, { label: string; desc: string }> = {
	archive_inactive_workspaces: {
		label: "Archive Inactive Workspaces",
		desc: "Archive workspaces that have had no activity for a given duration.",
	},
	rotate_api_keys: {
		label: "Rotate API Keys",
		desc: "High-risk: Revoke/reset API keys for matching workspaces. Password or MFA required.",
	},
	assign_role: {
		label: "Assign Role to Members",
		desc: "Bulk assign a role to workspace members matching the filter.",
	},
	delete_source_type_memories: {
		label: "Delete Memories by Source Type",
		desc: "Purge automated memories (e.g. scraper runs, podcasts) matching criteria.",
	},
	apply_tier: {
		label: "Apply Plan Tier to Workspaces",
		desc: "Upgrade or downgrade the plan tier across matching workspaces.",
	},
	revoke_membership: {
		label: "Revoke Member Access",
		desc: "Remove members from workspaces based on inactivity or role.",
	},
};

export function ActionSelector({
	value,
	onChange,
	isSuperadmin = true,
	disabled = false,
}: ActionSelectorProps) {
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
					Select Bulk Action
				</Label>
				{value && ACTION_METADATA[value]?.isHighRisk && (
					<Badge variant="destructive" className="text-xs">
						High Risk Action
					</Badge>
				)}
			</div>
			<Select
				value={value}
				onValueChange={(val) => onChange(val as BulkAction)}
				disabled={disabled}
			>
				<SelectTrigger id="bulk-action-select" className="w-full">
					<SelectValue placeholder="Choose an action to perform..." />
				</SelectTrigger>
				<SelectContent>
					{actions.map((action) => {
						const meta = ACTION_METADATA[action];
						const info = ACTION_LABELS[action];
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
