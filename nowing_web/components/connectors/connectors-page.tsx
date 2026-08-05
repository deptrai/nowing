"use client";

import { useAtom, useAtomValue } from "jotai";
import { useMemo } from "react";
import { importConnectorRequestAtom } from "@/atoms/connector-dialog/connector-dialog.atoms";
import { connectorsAtom } from "@/atoms/connectors/connector-query.atoms";
import { statusInboxItemsAtom } from "@/atoms/inbox/status-inbox.atom";
import { useIndexingConnectors } from "@/components/assistant-ui/connector-popup/hooks/use-indexing-connectors";
import { Spinner } from "@/components/ui/spinner";
import { isConnectorIndexingMetadata } from "@/contracts/types/inbox.types";
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
	const [importRequest, setImportRequest] = useAtom(importConnectorRequestAtom);

	const { data: queryConnectors, isPending: queryPending } = useAtomValue(connectorsAtom);
	const { connectors: syncConnectors, loading: syncLoading } = useConnectorsSync(workspaceId);
	const statusInboxItems = useAtomValue(statusInboxItemsAtom);

	const connectors = useMemo<SearchSourceConnector[]>(() => {
		if (syncConnectors.length > 0) return syncConnectors;
		return (queryConnectors ?? []) as SearchSourceConnector[];
	}, [syncConnectors, queryConnectors]);

	const isLoading = queryPending || syncLoading;

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

	const handleSelect = (connectorType: string) => {
		setImportRequest({ connectorType, mode: "auto" });
	};

	const handleBack = () => {
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
					selectedType={importRequest?.connectorType}
					isLoading={isLoading}
					onSelect={handleSelect}
				/>
			</div>
			<div className="flex-1 min-w-0 overflow-hidden">
				{importRequest ? (
					<ConnectorDetailPane
						request={importRequest}
						connectors={connectors}
						indexingConnectorIds={indexingConnectorIds}
						failedConnectorIds={failedConnectorIds}
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
