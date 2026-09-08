"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";
import { workspacesAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { usePermissionGate } from "@/atoms/members/members-query.atoms";
import { CANONICAL_PERMISSIONS } from "@/contracts/types/permissions.types";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { governanceApiService } from "@/lib/apis/governance-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { AuditLogPanel } from "./audit-log-panel";
import { DncPanel } from "./dnc-panel";
import { RetentionPolicyPanel } from "./retention-policy-panel";
import { RightToDeletePanel } from "./right-to-delete-panel";
import { SourceRiskTierPanel } from "./source-risk-tier-panel";
import { WorkspaceStatusPanel } from "./workspace-status-panel";

interface GovernanceConsoleProps {
	workspaceId: number;
}

export function GovernanceConsole({ workspaceId }: GovernanceConsoleProps) {
	const t = useTranslations("governance");
	const { data: workspacesData } = useAtomValue(workspacesAtom);
	const isOwner = useMemo(
		() => workspacesData?.find((w) => w.id === workspaceId)?.is_owner ?? false,
		[workspacesData, workspaceId]
	);
	const canUpdateSettings = usePermissionGate(CANONICAL_PERMISSIONS.SETTINGS_UPDATE);
	const canDeleteMemory = usePermissionGate(CANONICAL_PERMISSIONS.MEMORY_DELETE);
	const canEditGovernance = isOwner || canUpdateSettings;
	const canEditRightToDelete = isOwner || canDeleteMemory;

	const { data: overview, isLoading, refetch } = useQuery({
		queryKey: ["governance", "overview", workspaceId],
		queryFn: () => governanceApiService.getOverview(workspaceId),
		enabled: !!workspaceId,
	});

	const [activeTab, setActiveTab] = useState("retention");

	if (isLoading) {
		return (
			<div className="space-y-4 p-6">
				<Skeleton className="h-8 w-48" />
				<Skeleton className="h-10 w-full" />
				<Skeleton className="h-64 w-full" />
			</div>
		);
	}

	const canEdit = canEditGovernance;

	return (
		<div className="p-6 space-y-6">
			<div className="space-y-1">
				<h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
				<p className="text-sm text-muted-foreground">{t("description")}</p>
			</div>

			<Tabs value={activeTab} onValueChange={setActiveTab}>
				<TabsList className="grid w-full grid-cols-5">
					<TabsTrigger value="retention">{t("tabs.retention")}</TabsTrigger>
					<TabsTrigger value="source-tiers">{t("tabs.source_tiers")}</TabsTrigger>
					<TabsTrigger value="dnc">{t("tabs.dnc")}</TabsTrigger>
					<TabsTrigger value="audit-log">{t("tabs.audit_log")}</TabsTrigger>
					<TabsTrigger value="status">{t("tabs.status")}</TabsTrigger>
				</TabsList>

				<TabsContent value="retention" className="space-y-4">
					<RetentionPolicyPanel
						workspaceId={workspaceId}
						retention={overview?.retention_policy}
						canEdit={canEdit}
						onSaved={refetch}
					/>
				</TabsContent>

				<TabsContent value="source-tiers" className="space-y-4">
					<SourceRiskTierPanel
						workspaceId={workspaceId}
						tiers={overview?.source_risk_tiers ?? []}
						canEdit={canEdit}
						onChanged={refetch}
					/>
				</TabsContent>

				<TabsContent value="dnc" className="space-y-4">
					<DncPanel
						workspaceId={workspaceId}
						records={overview?.dnc_records ?? []}
						canEdit={canEdit}
						onChanged={refetch}
					/>
				</TabsContent>

				<TabsContent value="audit-log" className="space-y-4">
					<AuditLogPanel workspaceId={workspaceId} />
				</TabsContent>

				<TabsContent value="status" className="space-y-4">
					<WorkspaceStatusPanel
						workspaceId={workspaceId}
						status={overview?.workspace_status}
						canEdit={canEdit}
						onChanged={refetch}
					/>
					<RightToDeletePanel workspaceId={workspaceId} canEdit={canEditRightToDelete} />
				</TabsContent>
			</Tabs>
		</div>
	);
}
