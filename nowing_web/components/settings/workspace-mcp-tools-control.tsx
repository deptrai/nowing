"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { useCallback, useMemo } from "react";
import { toast } from "sonner";
import { updateWorkspaceMcpToolMutationAtom } from "@/atoms/workspaces/workspace-mutation.atoms";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import type { WorkspaceMcpTool } from "@/contracts/types/workspace.types";
import { workspacesApiService } from "@/lib/apis/workspaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";

interface WorkspaceMcpToolsControlProps {
	workspaceId: number;
	isOwner?: boolean;
	className?: string;
}

const groupLabels: Record<string, string> = {
	workspace: "Workspace",
	scraper: "Scrapers",
	run_history: "Run history",
	knowledge_base: "Knowledge base",
};

export function WorkspaceMcpToolsControl({
	workspaceId,
	isOwner,
	className,
}: WorkspaceMcpToolsControlProps) {
	const { mutateAsync: updateTool } = useAtomValue(updateWorkspaceMcpToolMutationAtom);

	const {
		data: tools,
		isLoading,
		isError,
		refetch,
	} = useQuery({
		queryKey: cacheKeys.workspaces.mcpTools(workspaceId),
		queryFn: () => workspacesApiService.getWorkspaceMcpTools(workspaceId),
		enabled: !!workspaceId,
	});

	const groupedTools = useMemo(() => {
		const groups: Record<string, WorkspaceMcpTool[]> = {};
		for (const tool of tools ?? []) {
			if (!groups[tool.group]) groups[tool.group] = [];
			groups[tool.group].push(tool);
		}
		return groups;
	}, [tools]);

	const handleToggle = useCallback(
		async (toolName: string, enabled: boolean) => {
			if (!isOwner) {
				toast.error("Only workspace owners can change MCP tool settings");
				return;
			}
			try {
				await updateTool({ id: workspaceId, tool_name: toolName, enabled });
			} catch (error) {
				console.error("Error updating MCP tool:", error);
				toast.error(error instanceof Error ? error.message : "Failed to update tool");
			}
		},
		[isOwner, updateTool, workspaceId]
	);

	if (isLoading || isOwner === undefined) {
		return (
			<div className={cn("space-y-4", className)}>
				<Skeleton className="h-4 w-40" />
				<div className="space-y-3">
					{["skeleton-1", "skeleton-2", "skeleton-3", "skeleton-4", "skeleton-5"].map((key) => (
						<div key={key} className="flex items-center justify-between">
							<Skeleton className="h-4 w-48" />
							<Skeleton className="h-6 w-11 rounded-full" />
						</div>
					))}
				</div>
			</div>
		);
	}

	if (isError) {
		return (
			<div className={cn("space-y-2", className)}>
				<Label>MCP tools</Label>
				<p className="text-xs text-destructive">Failed to load MCP tools.</p>
				<Button variant="outline" size="sm" onClick={() => refetch()}>
					Retry
				</Button>
			</div>
		);
	}

	return (
		<section aria-label="MCP tools" className={cn("space-y-6", className)}>
			<div className="space-y-1">
				<Label>MCP tools</Label>
				<p className="text-xs text-muted-foreground">
					Control which built-in MCP tools are available in this workspace.
				</p>
			</div>

			{Object.entries(groupedTools).map(([group, groupTools]) => (
				<div key={group} className="space-y-3">
					<h4 className="text-sm font-semibold">
						{groupLabels[group] ??
							group.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
					</h4>
					<div className="space-y-3">
						{groupTools.map((tool) => {
							const displayName = tool.name.replace(/_/g, " ");
							return (
								<div key={tool.name} className="flex items-center justify-between gap-4">
									<div className="min-w-0">
										<p className="text-sm font-medium truncate" title={tool.name}>
											{displayName}
										</p>
										{tool.is_system && (
											<p className="text-xs text-muted-foreground">Always enabled</p>
										)}
									</div>
									<Switch
										data-testid={`toggle-${tool.name}`}
										checked={tool.enabled}
										disabled={!isOwner || tool.is_system}
										onCheckedChange={(checked) => handleToggle(tool.name, checked)}
									/>
								</div>
							);
						})}
					</div>
				</div>
			))}
		</section>
	);
}
