"use client";

import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import { ConnectorCard } from "@/components/assistant-ui/connector-popup/components/connector-card";
import {
	CONNECTOR_DISPLAY_DEFINITIONS,
	DEPRECATED_CONNECTOR_TYPES,
} from "@/components/assistant-ui/connector-popup/constants/connector-constants";
import { useIsSelfHosted } from "@/components/providers/runtime-config";
import { Input } from "@/components/ui/input";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { getDocumentCountForConnector } from "@/components/assistant-ui/connector-popup/utils/connector-document-mapping";
import { usePlatform } from "@/hooks/use-platform";
import { useZeroDocumentTypeCounts } from "@/hooks/use-zero-document-type-counts";
import { groupConnectorsByType } from "@/lib/connectors/group-connectors-by-type";

interface OverviewPaneProps {
	workspaceId: string;
	connectors: SearchSourceConnector[];
	indexingConnectorIds: Set<number>;
	onSelect: (connectorType: string) => void;
}

type DeploymentFilterableConnector = {
	readonly id: string;
	readonly title: string;
	readonly description: string;
	readonly connectorType?: string;
	readonly selfHostedOnly?: boolean;
	readonly desktopOnly?: boolean;
};

export function OverviewPane({ workspaceId, connectors, indexingConnectorIds, onSelect }: OverviewPaneProps) {
	const [searchQuery, setSearchQuery] = useState("");
	const selfHosted = useIsSelfHosted();
	const { isDesktop } = usePlatform();
	const documentTypeCounts = useZeroDocumentTypeCounts(workspaceId);

	const connectedTypes = useMemo(
		() => new Set(connectors.map((c) => c.connector_type)),
		[connectors]
	);

	const groups = useMemo(
		() => groupConnectorsByType(connectors, { displayTypes: undefined, deprecatedTypes: DEPRECATED_CONNECTOR_TYPES }),
		[connectors]
	);
	const groupsByType = useMemo(
		() => new Map(groups.map((g) => [g.connectorType, g])),
		[groups]
	);

	const matchesSearch = (title: string, description: string) =>
		searchQuery.length === 0 ||
		title.toLowerCase().includes(searchQuery.toLowerCase()) ||
		description.toLowerCase().includes(searchQuery.toLowerCase());

	const passesDeploymentFilter = (c: DeploymentFilterableConnector) =>
		(!c.selfHostedOnly || selfHosted) && (!c.desktopOnly || isDesktop);

	const visibleDefinitions = useMemo(() => {
		return CONNECTOR_DISPLAY_DEFINITIONS.filter((c) => {
			if (!matchesSearch(c.title, c.description)) return false;
			if (!passesDeploymentFilter(c)) return false;
			// Deprecated connectors are hidden unless already connected.
			if (
				c.connectorType &&
				DEPRECATED_CONNECTOR_TYPES.has(c.connectorType) &&
				!connectedTypes.has(c.connectorType)
			) {
				return false;
			}
			return true;
		});
	}, [connectedTypes, selfHosted, isDesktop, searchQuery]);

	return (
		<div className="flex h-full flex-col">
			<div className="border-b p-3">
				<div className="relative">
					<Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
					<Input
						type="text"
						placeholder="Search integrations…"
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						className="w-full pl-9"
					/>
				</div>
			</div>
			<div className="flex-1 overflow-y-auto p-4">
				{visibleDefinitions.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-20 text-center">
						<Search className="size-8 text-muted-foreground mb-3" />
						<p className="text-sm text-muted-foreground">No integrations found</p>
						<p className="text-xs text-muted-foreground/60 mt-1">Try a different search term</p>
					</div>
				) : (
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						{visibleDefinitions.map((definition) => {
							const isConnected =
								!!definition.connectorType && connectedTypes.has(definition.connectorType);
							const group = definition.connectorType
								? groupsByType.get(definition.connectorType)
								: undefined;
							const accountCount = group?.connectors.length ?? 0;
							const documentCount = definition.connectorType
								? getDocumentCountForConnector(definition.connectorType, documentTypeCounts)
								: undefined;
							const isIndexing =
								!!definition.connectorType &&
								!!group?.connectors.some((c) => indexingConnectorIds.has(c.id));
							const isMCP = definition.connectorType === "MCP_CONNECTOR";

							return (
								<ConnectorCard
									key={definition.id}
									id={definition.id}
									title={definition.title}
									description={definition.description}
									connectorType={definition.connectorType}
									isConnected={isConnected}
									isConnecting={false}
									documentCount={documentCount}
									accountCount={isMCP ? undefined : accountCount}
									connectorCount={isMCP ? accountCount : undefined}
									isIndexing={isIndexing}
									deprecated={
										!!definition.connectorType &&
										DEPRECATED_CONNECTOR_TYPES.has(definition.connectorType)
									}
									onConnect={() =>
										definition.connectorType && onSelect(definition.connectorType)
									}
									onManage={() =>
										definition.connectorType && onSelect(definition.connectorType)
									}
								/>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
}
