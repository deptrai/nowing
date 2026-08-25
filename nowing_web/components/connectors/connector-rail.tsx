"use client";

import { useAtomValue } from "jotai";
import { Loader2, TriangleAlert } from "lucide-react";
import { useMemo } from "react";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { statusInboxItemsAtom } from "@/atoms/inbox/status-inbox.atom";
import { useIndexingConnectors } from "@/components/assistant-ui/connector-popup/hooks/use-indexing-connectors";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { isConnectorIndexingMetadata } from "@/contracts/types/inbox.types";
import { useConnectorsSync } from "@/hooks/use-connectors-sync";
import {
	type ConnectorGroup,
	groupConnectorsByType,
} from "@/lib/connectors/group-connectors-by-type";
import { cn } from "@/lib/utils";

interface ConnectorRailProps {
	workspaceId: string;
	selectedType?: string | null;
	isLoading?: boolean;
	onSelect: (connectorType: string) => void;
}

function useLiveConnectors(workspaceId: string) {
	const { data: queryConnectors } = useAtomValue(connectorsAtom);
	const { connectors: syncConnectors } = useConnectorsSync(workspaceId);

	return useMemo<SearchSourceConnector[]>(() => {
		if (syncConnectors.length > 0) return syncConnectors;
		return (queryConnectors ?? []) as SearchSourceConnector[];
	}, [syncConnectors, queryConnectors]);
}

function useConnectorHealth(connectors: SearchSourceConnector[]) {
	const statusInboxItems = useAtomValue(statusInboxItemsAtom);
	const { indexingConnectorIds } = useIndexingConnectors(connectors, statusInboxItems);

	const failedConnectorIds = useMemo(() => {
		const failed = new Set<number>();
		for (const item of statusInboxItems) {
			if (item.type !== "connector_indexing") continue;
			const metadata = isConnectorIndexingMetadata(item.metadata) ? item.metadata : null;
			if (!metadata) continue;
			if (metadata.status === "failed" || metadata.error_message) {
				failed.add(metadata.connector_id);
			}
		}
		return failed;
	}, [statusInboxItems]);

	return { indexingConnectorIds, failedConnectorIds };
}

export function getConnectorGroupHealth(
	group: ConnectorGroup,
	indexingConnectorIds: Set<number>,
	failedConnectorIds: Set<number>
): "syncing" | "failed" | "ok" {
	const ids = new Set(group.connectors.map((c) => c.id));
	for (const id of ids) {
		if (failedConnectorIds.has(id)) return "failed";
	}
	for (const id of ids) {
		if (indexingConnectorIds.has(id)) return "syncing";
	}
	return "ok";
}

export function ConnectorRail({
	workspaceId,
	selectedType,
	isLoading,
	onSelect,
}: ConnectorRailProps) {
	const connectors = useLiveConnectors(workspaceId);
	const { indexingConnectorIds, failedConnectorIds } = useConnectorHealth(connectors);

	const groups = useMemo(() => groupConnectorsByType(connectors), [connectors]);

	if (isLoading && !connectors.length) {
		return (
			<div className="flex h-full w-full flex-col items-center justify-center p-4 text-center">
				<Spinner size="sm" className="mb-2 text-muted-foreground" />
				<p className="text-xs text-muted-foreground">Loading connectors…</p>
			</div>
		);
	}

	return (
		<div className="flex h-full w-full flex-col border-r bg-panel">
			<div className="border-b px-3 py-2">
				<h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
					Connected integrations
				</h3>
			</div>
			<div className="flex-1 overflow-y-auto p-1.5">
				{groups.length === 0 ? (
					<p className="px-3 py-2 text-xs text-muted-foreground">No connected integrations yet.</p>
				) : (
					<div className="space-y-0.5">
						{groups.map((group) => {
							const health = getConnectorGroupHealth(
								group,
								indexingConnectorIds,
								failedConnectorIds
							);
							const isSelected = selectedType === group.connectorType;
							return (
								<Button
									key={group.connectorType}
									variant="ghost"
									size="sm"
									onClick={() => onSelect(group.connectorType)}
									className={cn(
										"w-full justify-start gap-2 px-2 py-1.5 h-auto text-left",
										isSelected && "bg-accent text-accent-foreground"
									)}
								>
									{getConnectorIcon(group.connectorType, "size-4 shrink-0")}
									<span className="flex-1 truncate text-xs font-medium">{group.title}</span>
									{group.connectors.length > 1 && (
										<span className="ml-1 text-[10px] tabular-nums text-muted-foreground">
											{group.connectors.length}
										</span>
									)}
									{health === "syncing" && (
										<Loader2
											className="size-3.5 shrink-0 animate-spin text-primary"
											aria-hidden="true"
										/>
									)}
									{health === "failed" && (
										<TriangleAlert
											className="size-3.5 shrink-0 text-destructive"
											aria-hidden="true"
										/>
									)}
								</Button>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
}
