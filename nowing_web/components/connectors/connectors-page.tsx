"use client";

import { useAtom, useAtomValue } from "jotai";
import { useMemo, useState } from "react";
import { importConnectorRequestAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { statusInboxItemsAtom } from "@/atoms/inbox/status-inbox.atom";
import { useIndexingConnectors } from "@/components/assistant-ui/connector-popup/hooks/use-indexing-connectors";
import { Spinner } from "@/components/ui/spinner";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { useConnectorsSync } from "@/hooks/use-connectors-sync";
import { cn } from "@/lib/utils";
import { ConnectorDetailPane } from "./connector-detail-pane";
import { ConnectorRail } from "./connector-rail";
import { OverviewPane } from "./overview-pane";

interface ConnectorsPageProps {
	workspaceId: string;
}

export function ConnectorsPage({ workspaceId }: ConnectorsPageProps) {
	// Local selection state — independent of importConnectorRequestAtom so the
	// detail pane stays mounted while the hook processes the request internally.
	const [selectedType, setSelectedType] = useState<string | null>(null);
	const [, setImportRequest] = useAtom(importConnectorRequestAtom);

	const { data: queryConnectors, isPending: queryPending } = useAtomValue(connectorsAtom);
	const { connectors: syncConnectors, loading: syncLoading } = useConnectorsSync(workspaceId);
	const statusInboxItems = useAtomValue(statusInboxItemsAtom);

	const connectors = useMemo<SearchSourceConnector[]>(() => {
		if (syncConnectors.length > 0) return syncConnectors;
		return (queryConnectors ?? []) as SearchSourceConnector[];
	}, [syncConnectors, queryConnectors]);

	const isLoading = queryPending || syncLoading;

	const { indexingConnectorIds } = useIndexingConnectors(connectors, statusInboxItems);

	const handleSelect = (connectorType: string) => {
		setSelectedType(connectorType);
		// Trigger the hook's auto-routing (0→connect, 1→edit, many→accounts)
		setImportRequest({ connectorType, mode: "auto" });
	};

	const handleBack = () => {
		setSelectedType(null);
		setImportRequest(null);
	};

	if (isLoading && connectors.length === 0) {
		return (
			<div className="flex h-full items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	return (
		<div className={cn("flex h-full w-full flex-col md:flex-row overflow-hidden")}>
			<div className="w-full md:w-64 shrink-0 border-b md:border-b-0 md:border-r">
				<ConnectorRail
					workspaceId={workspaceId}
					selectedType={selectedType}
					isLoading={isLoading}
					onSelect={handleSelect}
				/>
			</div>
			<div className="flex-1 min-w-0 overflow-hidden">
				{selectedType ? (
					<ConnectorDetailPane
						connectorType={selectedType}
						workspaceId={workspaceId}
						onBack={handleBack}
					/>
				) : (
					<OverviewPane
						workspaceId={workspaceId}
						connectors={connectors}
						indexingConnectorIds={indexingConnectorIds}
						onSelect={handleSelect}
					/>
				)}
			</div>
		</div>
	);
}
